import asyncio
import random
from pathlib import Path
from typing import Optional, Union
from google.protobuf.message import DecodeError
from concurrent.futures import ProcessPoolExecutor as Executor

from watchfs import watchfs_pb2
from watchfs.watchfs import watch_path
from watchfs.debounced_events import DebouncedEvent
from typing import AsyncIterator


class watch:
    """Monitor a file using rust's notify library"""

    def __init__(
        self,
        path: Union[Path, str],
        recursive: bool = True,
        stop: Optional[asyncio.Event] = None,
        debounce_millis: int = 100,
        port=None,
    ) -> AsyncIterator[DebouncedEvent]:
        self._path = path
        self._recursive = recursive
        self._stop = stop
        self._debounced_event = watchfs_pb2.DebouncedEvent()
        self._message_queue = asyncio.Queue()
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.rust_task = None
        self.port = None
        self._debounce_millis = debounce_millis

    def __aiter__(self) -> AsyncIterator[DebouncedEvent]:
        return self

    async def __anext__(self) -> DebouncedEvent:
        if self.reader is None:
            await self.open_stream()
            self.rust_task = asyncio.create_task(self.start_rust())
            while self.reader is None and not self.rust_task.done():
                await asyncio.sleep(0.01)
            self.message_receiver_task = asyncio.create_task(self.get_messages_from_rust(stop=self._stop))

        while self._stop is None or not self._stop.is_set() and not self.rust_task.done():
            if self._message_queue.empty():
                await asyncio.sleep(0.1)
            else:
                message = await self._message_queue.get()
                try:
                    self._debounced_event.ParseFromString(message)
                    debounced_event = DebouncedEvent(
                        path=self._debounced_event.path,
                        type=self._debounced_event.action,
                        error_message=self._debounced_event.error_message,
                    )
                    return debounced_event
                except DecodeError:
                    print(f"Could not decode {message}")
                finally:
                    self._message_queue.task_done()
        if not self.rust_task.done():
            await self.send_stop()
        try:
            await asyncio.gather(self.rust_task, return_exceptions=False)
        finally:
            self.writer.close()
            await self.writer.wait_closed()
        print("done rust task")
        asyncio.gather(self.message_receiver_task)
        print("done message receiver task")
        raise StopAsyncIteration

    async def send_stop(self):
        command = watchfs_pb2.WatchfsCommand()
        command.stop = True
        command_str = command.SerializeToString()
        command_len = len(command_str).to_bytes(2, byteorder="big")

        self.writer.write(command_len)
        self.writer.write(command_str)
        await self.writer.drain()

    async def get_messages_from_rust(self, stop: asyncio.Event):
        while not stop.is_set() and not self.rust_task.done():
            try:
                size = int.from_bytes(await asyncio.wait_for(self.reader.readexactly(2), 0.1), "big")
            except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                # IncompleteReadError if rust closes socket.
                # TimoutError if nothing sent in 0.1 seconds
                pass
            else:
                message = await self.reader.readexactly(size)
                await self._message_queue.put(message)

    async def open_stream(self):
        if self.port is None:
            while True:
                try:
                    self.port = random.randint(1024, 65535)
                    await asyncio.start_server(self.handle_connection, "127.0.0.1", self.port)
                    break
                except OSError:
                    pass
        else:
            await asyncio.start_server(self.handle_connection, "127.0.0.1", self.port)

    async def handle_connection(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def start_rust(self):
        loop = asyncio.get_running_loop()
        with Executor() as pool:
            rust_result = await loop.run_in_executor(
                pool, watch_path, f"127.0.0.1:{self.port}", str(self._path), self._recursive
            )
        return rust_result
