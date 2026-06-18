import contextlib
import hashlib
import os
import pathlib
import struct
import tempfile
import threading
import time
from datetime import datetime
from types import TracebackType
from typing import BinaryIO, cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import Expiry, to_timedelta

PathLike = pathlib.Path | str

_EXPIRY_HEADER_FORMAT = ">d"
_EXPIRY_HEADER_SIZE = struct.calcsize(_EXPIRY_HEADER_FORMAT)


class FileSystemCacheBackend(CacheBackendProtocol):
    path: pathlib.Path

    def __init__(self, path: PathLike) -> None:
        if isinstance(path, str):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        self.__lock = threading.RLock()

    def __get_real_path(self, key: bytes) -> pathlib.Path:
        return self.path / hashlib.sha256(key).hexdigest()

    def save(
        self,
        key: bytes,
        value: bytes,
        *,
        expire_seconds: Expiry,
    ) -> None:
        expire_at = datetime.now() + to_timedelta(expire_seconds)
        expire_timestamp = expire_at.timestamp()

        with self.__lock:
            realpath = self.__get_real_path(key)
            realpath.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: stage [8-byte expiry header][payload] in a sibling
            # temp file, fsync to disk, then ``os.replace`` it onto the real
            # path.  The expiry timestamp is encoded in the file itself so that
            # external mtime changes (touch, rsync, tar, etc.) cannot corrupt
            # the expiry state.
            fd, tmpname = tempfile.mkstemp(
                prefix=".tmp-",
                dir=str(realpath.parent),
            )
            tmppath = pathlib.Path(tmpname)
            try:
                with cast(BinaryIO, os.fdopen(fd, "wb")) as f:
                    f.write(
                        struct.pack(_EXPIRY_HEADER_FORMAT, expire_timestamp),
                    )
                    f.write(value)
                    f.flush()
                    os.fsync(f.fileno())
                tmppath.replace(realpath)
            except BaseException:
                with contextlib.suppress(FileNotFoundError):
                    tmppath.unlink()
                raise

    def load(self, key: bytes) -> bytes | None:
        path = self.__get_real_path(key)
        with contextlib.suppress(FileNotFoundError):
            if not self.__can_load(path):
                return None
            with cast(BinaryIO, path.open("rb")) as f:
                f.seek(_EXPIRY_HEADER_SIZE)
                return f.read()
        return None

    def __can_load(self, path: pathlib.Path) -> bool:
        return path.is_file() and not self.__delete_if_expired(path)

    def __read_expire_timestamp(self, path: pathlib.Path) -> float:
        with contextlib.suppress(OSError, struct.error), path.open("rb") as f:
            raw = f.read(_EXPIRY_HEADER_SIZE)
            return struct.unpack(_EXPIRY_HEADER_FORMAT, raw)[0]
        return float("-inf")

    def __is_expired(self, path: pathlib.Path) -> bool:
        return self.__read_expire_timestamp(path) < time.time()

    def exists(self, key: bytes) -> bool:
        path = self.__get_real_path(key)
        with self.__lock:
            return path.is_file() and not self.__is_expired(path)

    def delete(self, key: bytes) -> None:
        with self.__lock, contextlib.suppress(FileNotFoundError):
            self.__get_real_path(key).unlink()

    def delete_expired(self) -> int:
        with contextlib.suppress(FileNotFoundError):
            return sum(
                1
                for path in self.path.iterdir()
                if self.__delete_file_if_expired(path)
            )
        return 0

    def __delete_file_if_expired(self, path: pathlib.Path) -> bool:
        with contextlib.suppress(FileNotFoundError):
            return path.is_file() and self.__delete_if_expired(path)
        return False

    def __delete_if_expired(self, path: pathlib.Path) -> bool:
        with self.__lock:
            if self.__is_expired(path):
                path.unlink()
                return True
        return False

    def close(self) -> None:
        pass

    def __enter__(self) -> "FileSystemCacheBackend":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()
