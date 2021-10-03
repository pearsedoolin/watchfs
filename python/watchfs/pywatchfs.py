import asyncio
import random
from pathlib import Path
from typing import Optional, Union
from google.protobuf.message import DecodeError
from concurrent.futures import ProcessPoolExecutor as Executor

from watchfs import watchfs_pb2
from watchfs.watchfs import watch_path


class watch:
    """Monitor a file using rust's notify library"""

    def __init__(
        self,
        path: Union[Path, str],
        recursive: bool = True,
        stop: Optional[asyncio.Event] = None,
        port=None,
    ):
        self._path = path
        self._recursive = recursive
        self._stop = stop
        self._file_change = watchfs_pb2.FileChange()
        self._message_queue = asyncio.Queue()
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.rust_task = None
        self.port = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.reader is None:
            await self.open_stream()
            self.rust_task = asyncio.create_task(
                self.start_rust(f"127.0.0.1:{self.port}")
            )
            while self.reader is None:
                await asyncio.sleep(0.01)
            self.message_receiver_task = asyncio.create_task(
                self.get_messages_from_rust(stop=self._stop)
            )

        while self._stop is None or not self._stop.is_set():
            if self._message_queue.empty():
                await asyncio.sleep(0.01)
            if not self._message_queue.empty():
                message = await self._message_queue.get()
                try:
                    self._file_change.ParseFromString(message)
                    return self._file_change

                except DecodeError:
                    print(f"Could not decode {message}")

        # stop the listening function
        command = watchfs_pb2.WatchfsCommand()
        command.stop = True
        command_str = command.SerializeToString()
        command_len = len(command_str).to_bytes(2, byteorder="big")

        self.writer.write(command_len)
        self.writer.write(command_str)
        await self.writer.drain()

        print(await asyncio.gather(self.rust_task))

        self.writer.close()
        await self.writer.wait_closed()
        print("done rust task")
        asyncio.gather(self.message_receiver_task)
        print("done message receiver task")
        raise StopAsyncIteration

    async def get_messages_from_rust(self, stop: asyncio.Event):
        while not stop.is_set():
            try:
                size = int.from_bytes(
                    await asyncio.wait_for(self.reader.readexactly(2), 0.1), "big"
                )
            except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                # IncompleteReadError if rust closes socket.
                # TimoutError if nothing sent in 0.1 seconds
                pass
            else:
                message = await self.reader.readexactly(size)
                await self._message_queue.put(message)
        # TODO: call rust funtion that stops the watch

    async def open_stream(self):
        if self.port is None:
            while True:
                try:
                    self.port = random.randint(1024, 65535)
                    await asyncio.start_server(
                        self.handle_connection, "127.0.0.1", self.port
                    )
                    break
                except OSError as e:
                    pass
        else:
            await asyncio.start_server(self.handle_connection, "127.0.0.1", self.port)

    async def handle_connection(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def start_rust(self, address):
        loop = asyncio.get_running_loop()
        with Executor() as pool:
            rust_result = await loop.run_in_executor(pool, watch_path, address)
        return rust_result
