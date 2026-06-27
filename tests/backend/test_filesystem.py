import hashlib
import pathlib
import struct
import tempfile
import threading
import time
from datetime import datetime, tzinfo
from types import MethodType
from typing import BinaryIO, ClassVar, TextIO, cast

import pytest

from cachepot.backend import filesystem as filesystem_backend
from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.expire import to_timedelta

_ORIGINAL_PATH_OPEN = pathlib.Path.open
_ORIGINAL_PATH_UNLINK = pathlib.Path.unlink


class _FrozenDatetime(datetime):
    frozen_now: ClassVar["_FrozenDatetime"]

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "_FrozenDatetime":
        if tz is not None:
            return cls.frozen_now.replace(tzinfo=tz)
        return cls.frozen_now


def _cache_entry_path(cache_dir: pathlib.Path, key: bytes) -> pathlib.Path:
    return cache_dir / hashlib.sha256(key).hexdigest()


_EXPIRY_HEADER_FORMAT = ">d"
_EXPIRY_HEADER_SIZE = struct.calcsize(_EXPIRY_HEADER_FORMAT)


def _mark_expired(path: pathlib.Path) -> None:
    data = path.read_bytes()
    expired_at = time.time() - 60
    header = struct.pack(_EXPIRY_HEADER_FORMAT, expired_at)
    path.write_bytes(header + data[_EXPIRY_HEADER_SIZE:])


def _unlink_before_open(
    self: pathlib.Path,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
) -> BinaryIO | TextIO:
    self.unlink()
    return cast(
        BinaryIO | TextIO,
        _ORIGINAL_PATH_OPEN(
            self,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        ),
    )


class _UnlinkAfterConcurrentSave:
    __slots__ = ("realpath", "save_done", "unlink_started")

    def __init__(
        self,
        realpath: pathlib.Path,
        unlink_started: threading.Event,
        save_done: threading.Event,
    ) -> None:
        self.realpath = realpath
        self.unlink_started = unlink_started
        self.save_done = save_done

    def __get__(
        self,
        obj: pathlib.Path,
        _objtype: type[pathlib.Path] | None = None,
    ) -> MethodType:
        return MethodType(self, obj)

    def __call__(
        self,
        path: pathlib.Path,
        missing_ok: bool = False,
    ) -> None:
        if path == self.realpath:
            self.unlink_started.set()
            self.save_done.wait(timeout=0.2)
        _ORIGINAL_PATH_UNLINK(path, missing_ok=missing_ok)


def _save_after_unlink_starts(
    cachestore: FileSystemCacheBackend,
    key: bytes,
    unlink_started: threading.Event,
    save_done: threading.Event,
) -> None:
    assert unlink_started.wait(timeout=1)
    cachestore.save(key, b"new", expire_seconds=3600)
    save_done.set()


def test_delete_expired_does_not_remove_concurrent_fresh_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        key = b"race"
        cachestore.save(key, b"old", expire_seconds=60)
        realpath = _cache_entry_path(cache_dir, key)
        _mark_expired(realpath)
        unlink_started = threading.Event()
        save_done = threading.Event()

        monkeypatch.setattr(
            pathlib.Path,
            "unlink",
            _UnlinkAfterConcurrentSave(realpath, unlink_started, save_done),
        )

        writer = threading.Thread(
            target=_save_after_unlink_starts,
            args=(cachestore, key, unlink_started, save_done),
        )
        writer.start()
        deleted = cachestore.delete_expired()
        writer.join(timeout=1)

        assert not writer.is_alive()
        assert deleted == 1
        assert cachestore.load(key) == b"new"


def test_various_pathlike() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = FileSystemCacheBackend(pathlib.Path(tmpdir))
        assert cachestore.load(b"1") is None
        cachestore.save(b"1", b"2", expire_seconds=1)
        assert cachestore.load(b"1") == b"2"
        cachestore.delete(b"1")
        assert cachestore.load(b"1") is None

    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = FileSystemCacheBackend(tmpdir)
        assert cachestore.load(b"3") is None
        cachestore.save(b"3", b"4", expire_seconds=1)
        assert cachestore.load(b"3") == b"4"
        cachestore.delete(b"3")
        assert cachestore.load(b"3") is None


def test_save_creates_missing_cache_directory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir) / "missing-cache"
        cachestore = FileSystemCacheBackend(cache_dir)

        assert not cache_dir.exists()
        cachestore.save(b"1", b"2", expire_seconds=1)

        assert cache_dir.is_dir()
        assert cachestore.load(b"1") == b"2"


def test_expire() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = FileSystemCacheBackend(pathlib.Path(tmpdir))
        cachestore.save(b"1", b"2", expire_seconds=1)
        assert cachestore.load(b"1") == b"2"
        time.sleep(2)
        assert cachestore.load(b"1") is None


def test_fractional_expire_seconds_preserves_subsecond_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = _FrozenDatetime(2026, 5, 25, 10, 30, 15, 250000)
    expire_seconds = 0.5
    _FrozenDatetime.frozen_now = now
    monkeypatch.setattr(filesystem_backend, "datetime", _FrozenDatetime)

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        key = b"fractional"
        cachestore.save(key, b"value", expire_seconds=expire_seconds)
        realpath = _cache_entry_path(cache_dir, key)
        expected_expire_at = now.timestamp() + expire_seconds

        raw_header = realpath.read_bytes()[:_EXPIRY_HEADER_SIZE]
        (stored_expire_at,) = struct.unpack(
            _EXPIRY_HEADER_FORMAT,
            raw_header,
        )
        assert stored_expire_at == pytest.approx(expected_expire_at)

        monkeypatch.setattr(
            filesystem_backend.time,
            "time",
            lambda: expected_expire_at + 0.001,
        )

        assert cachestore.load(key) is None


def test_load_returns_none_when_entry_disappears_before_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        key = b"race"
        cachestore.save(key, b"value", expire_seconds=60)
        realpath = _cache_entry_path(cache_dir, key)
        assert realpath.exists()

        monkeypatch.setattr(pathlib.Path, "open", _unlink_before_open)

        assert cachestore.load(key) is None


def test_save_leaves_no_temp_files() -> None:
    """The atomic-rename path should leave the cache directory holding
    only the final cache entries after a successful save."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        cachestore.save(b"k1", b"v1", expire_seconds=60)
        cachestore.save(b"k2", b"v2", expire_seconds=60)

        names = sorted(p.name for p in cache_dir.iterdir())
        assert len(names) == 2
        assert all(not n.startswith(".tmp-") for n in names)


def test_save_sets_expiration_header_on_overwrite() -> None:
    """Overwriting an entry must end with the new expiration header, not
    an in-flight temporary timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        cachestore.save(b"k", b"old", expire_seconds=1)
        time.sleep(1.1)
        # The old entry is now expired; overwrite with a far-future TTL.
        cachestore.save(b"k", b"new", expire_seconds=3600)

        (entry,) = [p for p in cache_dir.iterdir() if p.is_file()]
        future_threshold = (datetime.now() + to_timedelta(60)).timestamp()
        raw_header = entry.read_bytes()[:_EXPIRY_HEADER_SIZE]
        (expire_ts,) = struct.unpack(_EXPIRY_HEADER_FORMAT, raw_header)
        assert expire_ts >= future_threshold
        assert cachestore.load(b"k") == b"new"


def test_load_deletes_expired_entry() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        key = b"expired"
        cachestore.save(key, b"value", expire_seconds=60)
        realpath = _cache_entry_path(cache_dir, key)
        _mark_expired(realpath)

        assert realpath.exists()
        assert cachestore.load(key) is None
        assert not realpath.exists()


def test_delete_expired() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        cachestore.save(b"expired", b"value", expire_seconds=60)
        cachestore.save(b"live", b"value", expire_seconds=60)
        expired_path = _cache_entry_path(cache_dir, b"expired")
        live_path = _cache_entry_path(cache_dir, b"live")
        _mark_expired(expired_path)

        deleted = cachestore.delete_expired()

        assert deleted == 1
        assert not expired_path.exists()
        assert live_path.exists()
        assert cachestore.load(b"live") == b"value"
        assert cachestore.delete_expired() == 0


def test_exists() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = FileSystemCacheBackend(pathlib.Path(tmpdir))
        assert not cachestore.exists(b"k")
        cachestore.save(b"k", b"v", expire_seconds=60)
        assert cachestore.exists(b"k")
        cachestore.delete(b"k")
        assert not cachestore.exists(b"k")


def test_filesystem_backend_is_context_manager() -> None:
    """FileSystemCacheBackend must work as a context manager."""
    with tempfile.TemporaryDirectory() as tmpdir, FileSystemCacheBackend(
        pathlib.Path(tmpdir),
    ) as backend:
        backend.save(b"k", b"v", expire_seconds=60)
        assert backend.load(b"k") == b"v"


def test_exists_does_not_delete_expired_entry() -> None:
    """exists() must be side-effect-free: calling it on an expired entry
    must not delete the file from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        key = b"expired"
        cachestore.save(key, b"value", expire_seconds=60)
        realpath = _cache_entry_path(cache_dir, key)
        _mark_expired(realpath)

        assert not cachestore.exists(key)
        assert realpath.exists(), "exists() must not delete the file"
