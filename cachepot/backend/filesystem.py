import hashlib
import os
import pathlib
import time
from datetime import datetime
from typing import BinaryIO, Optional, Union, cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import ExpireSeconds, to_timedelta

PathLike = Union[pathlib.Path, str]


class FileSystemCacheBackend(CacheBackendProtocol):
    path: pathlib.Path

    def __init__(self, path: PathLike):
        if isinstance(path, str):
            self.path = pathlib.Path(path)
        else:
            self.path = path

    def __get_real_path(self, key: bytes) -> pathlib.Path:
        return self.path / hashlib.sha256(key).hexdigest()

    def save(self, key: bytes, value: bytes, expire_seconds: ExpireSeconds) -> None:
        expire_at = datetime.now() + to_timedelta(expire_seconds)
        expire_timestamp = time.mktime(expire_at.timetuple())

        realpath = self.__get_real_path(key)
        with cast(BinaryIO, realpath.open("wb")) as f:
            f.write(value)
        os.utime(str(realpath), (expire_timestamp, expire_timestamp))

    def load(self, key: bytes) -> Optional[bytes]:
        path = self.__get_real_path(key)
        if not path.exists() or path.is_dir():
            return None
        if path.stat().st_mtime < time.mktime(datetime.now().timetuple()):
            return None
        with cast(BinaryIO, path.open("rb")) as f:
            return f.read()

    def delete(self, key: bytes) -> None:
        try:
            self.__get_real_path(key).unlink()
        except FileNotFoundError:
            pass
