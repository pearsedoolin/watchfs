import asyncio
from watchfs import watch


async def run_watcher(stop):
    async for file_change in watch("somefile", stop=stop):
        print(file_change)


async def start_tasks():
    stop = asyncio.Event()
    watcher_task = asyncio.create_task(run_watcher(stop))
    await asyncio.sleep(5)
    stop.set()
    await asyncio.gather(watcher_task)
    print("done")


if __name__ == "__main__":
    # Using this instead of asyncio.run(start_tasks()) because of his bug: https://bugs.python.org/issue39232
    asyncio.run(start_tasks())
