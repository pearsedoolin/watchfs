from __future__ import annotations
import asyncio
import random
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor as Executor
from contextlib import asynccontextmanager
from watchfs.watchfs import watch_path


@asynccontextmanager
async def start_watch(*args, **kwargs):
    watcher = Watcher(*args, **kwargs)
    await watcher.start()
    try:
        yield watcher
    finally:
        await watcher.stop()


class Watcher:
    """Monitor a file using rust's notify library"""

    def __init__(
        self,
        path: Path | str,
        recursive: bool = True,
        stop: asyncio.Event | None = None,
        port=None,
    ):
        self._path = path
        self._recursive = recursive
        self._stop = stop or asyncio.Event()
        self._message_queue = asyncio.Queue()
        self.socket_connected = asyncio.Event()
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.rust_task = None
        self.port = port
        self.message_receiver_task = None

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        while not self._stop.is_set() and not self.rust_task.done():
            if self._message_queue.empty():
                await asyncio.sleep(0.1)
            else:
                message = await self._message_queue.get()
                return json.loads(message)
        raise StopAsyncIteration

    async def start(self):
        await self.open_stream()
        self.rust_task = asyncio.create_task(self.start_rust())
        await self.socket_connected.wait()
        ready = await self.receive_str()
        assert ready == "ready"
        self.message_receiver_task = asyncio.create_task(self.get_messages_from_rust(stop=self._stop))

    async def stop(self):
        self._stop.set()
        asyncio.gather(self.message_receiver_task)
        await self.send_str("stop")
        await asyncio.gather(self.rust_task)
        self.writer.close()
        await self.writer.wait_closed()

    async def send_str(self, s):
        command_len = len(s).to_bytes(2, byteorder="big")
        self.writer.write(command_len)
        self.writer.write(s.encode())
        await self.writer.drain()

    async def receive_str(self) -> str:
        size = int.from_bytes(await asyncio.wait_for(self.reader.readexactly(2), 0.1), "big")
        message = await self.reader.readexactly(size)
        return message.decode()

    async def get_messages_from_rust(self, stop: asyncio.Event):
        while not stop.is_set() and not self.rust_task.done():
            try:
                message = await asyncio.wait_for(self.receive_str(), 0.1)
                await self._message_queue.put(message)
            except asyncio.TimeoutError:
                pass

    def handle_connection(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.socket_connected.set()

    async def open_stream(self):
        if self.port is None:
            while True:
                self.port = random.randint(1024, 65535)
                await asyncio.wait_for(asyncio.start_server(self.handle_connection, "127.0.0.1", self.port), 1)
                break
        else:
            await asyncio.start_server(self.handle_connection, "127.0.0.1", self.port)

    async def start_rust(self):
        loop = asyncio.get_running_loop()
        with Executor() as pool:
            rust_result = await loop.run_in_executor(
                pool, watch_path, f"127.0.0.1:{self.port}", str(self._path), self._recursive
            )
        return rust_result
