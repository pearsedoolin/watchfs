import asyncio
from pathlib import Path
from typing import Optional, Union
from google.protobuf.message import DecodeError
import watchfs_pb2
from watchfs import watch_path

import random
from concurrent.futures import ProcessPoolExecutor as Executor


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
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.watch_task = None
        self.port = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self.open_stream()
        self.watch_task = asyncio.create_task(self.start_rust(f"127.0.0.1:{self.port}"))

        while self.reader is None:
            await asyncio.sleep(0.01)

        print("now waiting for something from rust")
        while self._stop is None or not self._stop.is_set():
            size = int.from_bytes(await self.reader.readexactly(2), "big")
            message = await self.reader.readexactly(size)
            try:
                self._file_change.ParseFromString(message)
                return self._file_change
            except DecodeError:
                print(f"Could not decode {message}")

        self.writer.close()
        await self.writer.wait_closed()
        asyncio.gather(self.watch_task)
        raise StopAsyncIteration()

    async def open_stream(self):
        if self.port is None:
            while True:
                try:
                    self.port = random.randint(1024, 65535)
                    server = await asyncio.start_server(
                        self.handle_connection, "127.0.0.1", self.port
                    )
                    break
                except OSError as e:
                    pass
        else:
            server = await asyncio.start_server(
                self.handle_connection, "127.0.0.1", self.port
            )

    async def handle_connection(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def start_rust(self, address):
        loop = asyncio.get_running_loop()
        with Executor() as pool:
            rust_result = await loop.run_in_executor(pool, watch_path, address)
        print(rust_result)


async def run_watcher():
    async for file_change in watch("somefile"):
        print(file_change)


if __name__ == "__main__":
    asyncio.run(run_watcher())
