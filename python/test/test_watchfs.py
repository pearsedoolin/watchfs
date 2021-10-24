from __future__ import annotations
import asyncio
import pytest
from watchfs import prepare_watch
from watchfs import DebouncedEventTypes, DebouncedEvent
from pathlib import Path
from unittest.mock import Mock


async def run_watcher(
    path: Path | str,
    ready: asyncio.Event,
    recursive: bool = True,
    debounce_millis: int = 100,
    port=None,
    stop: asyncio.Event = None,
) -> DebouncedEvent:
    async with prepare_watch(
        path, stop=stop, recursive=recursive, debounce_millis=debounce_millis, port=port
    ) as watcher:
        ready.set()
        async for file_change in watcher:
            if stop is None:
                return file_change
    return file_change


@pytest.mark.parametrize("port", [None, 50338, 3056])
@pytest.mark.asyncio
async def test_create_file_with_stop_event(tmp_path, ready_event, stop_event, port):
    if port == "busy":
        port = 5036
        asyncio.create_task(asyncio.start_server(Mock(), "127.0.0.1", port))
        await asyncio.sleep(1)

    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event, port=port, stop=stop_event))

    await ready_event.wait()
    test_file = tmp_path / "test_file"
    test_file.touch()
    await asyncio.sleep(0.5)

    stop_event.set()
    file_change = (await asyncio.gather(watch_task))[0]
    assert file_change.type == DebouncedEventTypes.CREATE
    assert file_change.path == tmp_path / test_file
    assert file_change.error_message == ""


@pytest.mark.asyncio
async def test_port_busy(tmp_path, ready_event):
    port = 5036
    asyncio.create_task(asyncio.start_server(Mock(), "127.0.0.1", port))
    await asyncio.sleep(1)
    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event, port=port))
    with pytest.raises(OSError):
        await asyncio.gather(watch_task)


@pytest.mark.asyncio
async def test_async_create_no_stop_event(tmp_path, ready_event):
    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event))
    await ready_event.wait()
    test_file = tmp_path / "test_file"
    test_file.touch()

    file_change = (await asyncio.gather(watch_task))[0]
    assert file_change.type == DebouncedEventTypes.CREATE
    assert file_change.path == test_file
    assert file_change.error_message == ""
