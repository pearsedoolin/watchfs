
[![build](https://github.com/pearsedoolin/watchfs/actions/workflows/ci.yml/badge.svg)](https://github.com/pearsedoolin/watchfs/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/gh/pearsedoolin/watchfs/branch/main/graph/badge.svg)](https://codecov.io/gh/pearsedoolin/watchfs)
[![license](https://img.shields.io/github/license/pearsedoolin/watchfs)]((https://github.com/pearsedoolin/watchfs/blob/master/LICENSE))
[![snyk](https://snyk.io/test/github/pearsedoolin/watchfs/badge.svg)](https://snyk.io/)

# Watchfs

A python file system watcher that uses the rust [notify](https://docs.rs/notify/4.0.17/notify/) crate.

## Example

```python
import asyncio
import watchfs

async def my_async_file_watcher():
    async with watchfs.start_watch("path/to/watch") as watcher:
        async for file_change in watcher:
            print(file_change)

asyncio.run(my_async_file_watcher)
```
