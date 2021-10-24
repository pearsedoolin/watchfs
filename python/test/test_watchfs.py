from __future__ import annotations
import asyncio
import pytest
from watchfs import prepare_watch
from watchfs import DebouncedEventTypes, DebouncedEvent
from pathlib import Path
from unittest.mock import Mock
import stat
import platform


async def run_watcher(
    path: Path | str,
    ready: asyncio.Event,
    recursive: bool = True,
    debounce_millis: int = 100,
    port=None,
    stop: asyncio.Event = None,
    expected_events: int = 1,
) -> DebouncedEvent:
    async with prepare_watch(
        path, stop=stop, recursive=recursive, debounce_millis=debounce_millis, port=port
    ) as watcher:
        ready.set()
        file_changes = []
        async for file_change in watcher:
            file_changes.append(file_change)
            if stop is None and len(file_changes) == expected_events:
                break
    return file_changes


@pytest.mark.parametrize("port", [None, 50337])
@pytest.mark.parametrize("use_stop_event", [True, False])
@pytest.mark.asyncio
async def test_create_file(tmp_path, ready_event, use_stop_event, port):
    stop_event = asyncio.Event() if use_stop_event else None
    if port == "busy":
        port = 5036
        asyncio.create_task(asyncio.start_server(Mock(), "127.0.0.1", port))
        await asyncio.sleep(1)

    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event, port=port, stop=stop_event))

    await ready_event.wait()
    test_file = tmp_path / "test_file"
    test_file.touch()
    if stop_event:
        await asyncio.sleep(0.5)
        stop_event.set()
    file_change = (await asyncio.gather(watch_task))[0][0]
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
@pytest.mark.parametrize("write_mode", ["w", "a"])
@pytest.mark.parametrize("debounce_millis", [1, 300])
async def test_write(tmp_path, ready_event, write_mode, debounce_millis):
    stop_event = asyncio.Event()
    test_file = tmp_path / "test_file"
    test_file.touch()
    watch_task = asyncio.create_task(
        run_watcher(tmp_path, ready_event, stop=stop_event, debounce_millis=debounce_millis)
    )
    await ready_event.wait()

    with test_file.open(write_mode) as file_handle:
        file_handle.write("test")

    await asyncio.sleep(1)
    stop_event.set()

    file_changes = (await asyncio.gather(watch_task))[0]
    expected_event_types = [DebouncedEventTypes.NOTICEWRITE, DebouncedEventTypes.WRITE]

    assert len(file_changes) == len(expected_event_types)
    for file_change, expected_type in zip(file_changes, expected_event_types):
        assert file_change.type == expected_type
        assert file_change.path == tmp_path / test_file
        assert file_change.error_message == ""


@pytest.mark.skipif(platform.system() == "Windows", reason="chmod not supported on windows")
@pytest.mark.asyncio
async def test_chmod(tmp_path, ready_event):
    stop_event = asyncio.Event()
    test_file = tmp_path / "test_file"
    test_file.touch()
    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event, stop=stop_event))
    await ready_event.wait()

    mode = test_file.stat().st_mode
    test_file.chmod(mode ^ stat.S_IWRITE)

    await asyncio.sleep(1)
    stop_event.set()

    file_changes = (await asyncio.gather(watch_task))[0]
    expected_event_types = [DebouncedEventTypes.CHMOD]
    assert len(file_changes) == len(expected_event_types)
    for file_change, expected_type in zip(file_changes, expected_event_types):
        assert file_change.type == expected_type
        assert file_change.path == tmp_path / test_file
        assert file_change.error_message == ""


@pytest.mark.asyncio
async def test_remove(tmp_path, ready_event):
    stop_event = asyncio.Event()
    test_file = tmp_path / "test_file"
    test_file.touch()
    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event, stop=stop_event))
    await ready_event.wait()

    test_file.unlink()

    await asyncio.sleep(1)
    stop_event.set()

    file_changes = (await asyncio.gather(watch_task))[0]
    expected_event_types = [DebouncedEventTypes.NOTICEREMOVE, DebouncedEventTypes.REMOVE]
    assert len(file_changes) == len(expected_event_types)
    for file_change, expected_type in zip(file_changes, expected_event_types):
        assert file_change.type == expected_type
        assert file_change.path == tmp_path / test_file
        assert file_change.error_message == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_file, expected_event_types",
    [
        ("test_file", [DebouncedEventTypes.NOTICEREMOVE, DebouncedEventTypes.REMOVE, DebouncedEventTypes.CREATE]),
        (
            "test/test_file2",
            [
                DebouncedEventTypes.NOTICEREMOVE,
                DebouncedEventTypes.NOTICEWRITE,
                DebouncedEventTypes.RENAME,
                DebouncedEventTypes.WRITE,
            ],
        ),
        (
            "test/test/test_file",
            [
                DebouncedEventTypes.NOTICEREMOVE,
                DebouncedEventTypes.NOTICEWRITE,
                DebouncedEventTypes.REMOVE,
                DebouncedEventTypes.CREATE,
                DebouncedEventTypes.WRITE,
            ],
        ),
    ],
)
async def test_rename(tmp_path, ready_event, new_file, expected_event_types):

    stop_event = asyncio.Event()
    test_file = tmp_path / "test" / "test_file"
    test_file.parent.mkdir(exist_ok=True, parents=True)

    test_file.touch()

    new_path = tmp_path / new_file
    new_path.parent.mkdir(exist_ok=True, parents=True)

    watch_task = asyncio.create_task(run_watcher(tmp_path, ready_event, stop=stop_event, debounce_millis=1000))
    await ready_event.wait()

    test_file.rename(new_path)

    await asyncio.sleep(2)
    stop_event.set()

    file_changes = (await asyncio.gather(watch_task))[0]
    assert len(file_changes) == len(expected_event_types)
    for file_change, expected_type in zip(file_changes, expected_event_types):
        assert file_change.type == expected_type
        if file_change.type in [
            DebouncedEventTypes.NOTICEREMOVE,
            DebouncedEventTypes.REMOVE,
            DebouncedEventTypes.RENAME,
        ]:
            assert file_change.path == test_file
        elif file_change.type in [DebouncedEventTypes.NOTICEWRITE, DebouncedEventTypes.WRITE]:
            assert file_change.path == new_path.parent
        else:
            assert file_change.path == new_path
        assert file_change.error_message == ""
