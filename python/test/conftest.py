import pytest
from pathlib import Path


@pytest.fixture
def tmp_path(tmpdir):
    return Path(tmpdir)
