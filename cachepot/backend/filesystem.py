import contextlib
import hashlib
import os
import pathlib
import tempfile
import time
from datetime import datetime
from typing import BinaryIO, cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import ExpireSeconds, to_timedelta

PathLike = pathlib.Path | str


class FileSystemCacheBackend(CacheBackendProtocol):
    path: pathlib.Path

    def __init__(self, path: PathLike) -> None:
        if isinstance(path, str):
            self.path = pathlib.Path(path)
        else:
            self.path = path

    def __get_real_path(self, key: bytes) -> pathlib.Path:
        return self.path / hashlib.sha256(key).hexdigest()

    def save(
        self,
        key: bytes,
        value: bytes,
        expire_seconds: ExpireSeconds,
    ) -> None:
        expire_at = datetime.now() + to_timedelta(expire_seconds)
        expire_timestamp = time.mktime(expire_at.timetuple())

        realpath = self.__get_real_path(key)
        realpath.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: stage the payload in a sibling temp file, stamp
        # its mtime to the expiration time, then ``os.replace`` it onto
        # the final path. A crash before the rename leaves the temp file
        # behind but never exposes a partial or stale-mtime cache entry
        # at the real path.
        fd, tmpname = tempfile.mkstemp(
            prefix=".tmp-",
            dir=str(realpath.parent),
        )
        tmppath = pathlib.Path(tmpname)
        try:
            with cast(BinaryIO, os.fdopen(fd, "wb")) as f:
                f.write(value)
            os.utime(str(tmppath), (expire_timestamp, expire_timestamp))
            tmppath.replace(realpath)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                tmppath.unlink()
            raise

    def load(self, key: bytes) -> bytes | None:
        path = self.__get_real_path(key)
        if not self.__can_load(path):
            return None
        with cast(BinaryIO, path.open("rb")) as f:
            return f.read()

    def __can_load(self, path: pathlib.Path) -> bool:
        return path.is_file() and not self.__is_expired(path)

    def __is_expired(self, path: pathlib.Path) -> bool:
        return path.stat().st_mtime < time.mktime(datetime.now().timetuple())

    def delete(self, key: bytes) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.__get_real_path(key).unlink()
