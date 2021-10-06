import asyncio
import pytest
from watchfs import watch
from watchfs import DebouncedEventTypes, DebouncedEvent
from pathlib import Path


async def run_watcher(path: Path, stop_event: asyncio.Event) -> DebouncedEvent:
    async for file_change in watch(path, stop=stop_event):
        print(file_change)
    return file_change


async def wait_then_stop(stop_event: asyncio.Event):
    await asyncio.sleep(10)
    stop_event.set()


async def start_tasks():
    stop_event = asyncio.Event()
    watcher_task = asyncio.create_task(run_watcher(stop_event))
    stop_task = asyncio.create_task(wait_then_stop(stop_event))
    await asyncio.gather(watcher_task)
    stop_task.cancel()
    print("done")


@pytest.mark.asyncio
async def test_async_create(tmp_path):
    stop_event = asyncio.Event()
    watch_task = asyncio.create_task(run_watcher(tmp_path, stop_event))
    await asyncio.sleep(1)
    test_file_name = "test_file"
    (tmp_path / test_file_name).touch()
    await asyncio.sleep(1)

    stop_event.set()
    file_change = (await asyncio.gather(watch_task))[0]
    assert file_change.type == DebouncedEventTypes.CREATE
    assert file_change.path == tmp_path / test_file_name
    assert file_change.error_message == ""


# if __name__ == "__main__":
#     # Using this instead of asyncio.run(start_tasks()) because of his bug: https://bugs.python.org/issue39232
#     asyncio.run(start_tasks())
