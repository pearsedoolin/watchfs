import asyncio
import random
from pathlib import Path
from typing import Optional, Union
from concurrent.futures import ProcessPoolExecutor as Executor

from watchfs import watchfs_pb2
from watchfs.watchfs import watch_path
from watchfs.debounced_events import DebouncedEvent
from contextlib import asynccontextmanager


@asynccontextmanager
async def prepare_watch(*args, **kwargs):
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
        path: Union[Path, str],
        recursive: bool = True,
        stop: Optional[asyncio.Event] = None,
        debounce_millis: int = 100,
        port=None,
    ):
        self._path = path
        self._recursive = recursive
        self._stop = stop or asyncio.Event()
        self._debounced_event = watchfs_pb2.DebouncedEvent()
        self._message_queue = asyncio.Queue()
        self.socket_opened = asyncio.Event()
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.rust_task = None
        self.port = port
        self.message_receiver_task = None
        self._debounce_millis = debounce_millis

    def __aiter__(self):
        return self

    async def __anext__(self) -> DebouncedEvent:
        while not self._stop.is_set() and not self.rust_task.done():
            if self._message_queue.empty():
                await asyncio.sleep(0.1)
            else:
                message = await self._message_queue.get()
                self._debounced_event.ParseFromString(message)
                debounced_event = DebouncedEvent(
                    path=self._debounced_event.path,
                    type=self._debounced_event.action,
                    error_message=self._debounced_event.error_message,
                )
                self._message_queue.task_done()
                return debounced_event
        asyncio.gather(self.message_receiver_task)
        raise StopAsyncIteration

    async def start(self):
        await self.open_stream()
        self.start_rust_task()
        await self.socket_opened.wait()
        self.listen_for_rust_messages()

    async def stop(self):
        if not self.rust_task.done():
            await self.stop_rust_task()
        try:
            await asyncio.gather(self.rust_task)
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def stop_rust_task(self):
        command = watchfs_pb2.WatchfsCommand()
        command.stop = True
        command_str = command.SerializeToString()
        command_len = len(command_str).to_bytes(2, byteorder="big")

        self.writer.write(command_len)
        self.writer.write(command_str)
        await self.writer.drain()

    def listen_for_rust_messages(self):
        self.message_receiver_task = asyncio.create_task(self.get_messages_from_rust(stop=self._stop))

    async def get_messages_from_rust(self, stop: asyncio.Event):
        while not stop.is_set() and not self.rust_task.done():
            try:
                size = int.from_bytes(await asyncio.wait_for(self.reader.readexactly(2), 0.1), "big")
            except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                # IncompleteReadError if rust closes socket.
                # TimeoutError if nothing sent in 0.1 seconds
                pass
            else:
                message = await self.reader.readexactly(size)
                await self._message_queue.put(message)

    def handle_connection(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.socket_opened.set()

    async def open_stream(self):
        if self.port is None:
            while True:
                self.port = random.randint(1024, 65535)
                await asyncio.wait_for(asyncio.start_server(self.handle_connection, "127.0.0.1", self.port), 1)
                break
        else:
            await asyncio.start_server(self.handle_connection, "127.0.0.1", self.port)

    def start_rust_task(self):
        self.rust_task = asyncio.create_task(self.start_rust())

    async def start_rust(self):
        loop = asyncio.get_running_loop()
        with Executor() as pool:
            rust_result = await loop.run_in_executor(
                pool, watch_path, f"127.0.0.1:{self.port}", str(self._path), self._debounce_millis, self._recursive
            )
        return rust_result
