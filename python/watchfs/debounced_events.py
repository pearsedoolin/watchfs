from enum import Enum
from pathlib import Path
from typing import Optional, Union


class DebouncedEventTypes(Enum):
    NOTICEWRITE = 0
    NOTICEREMOVE = 1
    CREATE = 2
    WRITE = 3
    CHMOD = 4
    REMOVE = 5
    RENAME = 6
    RESCAN = 7
    ERROR = 8


class DebouncedEvent:
    def __init__(self, path: Union[str, Path], type: int, error_message: Optional[str]):
        self.path: Path = Path(path)
        self.type: DebouncedEventTypes = DebouncedEventTypes(type)
        self.error_message = error_message
