import asyncio

import pytest
from pathlib import Path


@pytest.fixture
def tmp_path(tmpdir):
    return Path(tmpdir)


@pytest.fixture()
def ready_event():
    return asyncio.Event()
