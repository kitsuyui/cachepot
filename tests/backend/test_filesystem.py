import hashlib
import os
import pathlib
import tempfile
import time
from datetime import datetime
from typing import BinaryIO, TextIO, cast

import pytest

from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.expire import to_timedelta

_ORIGINAL_PATH_OPEN = pathlib.Path.open


def _cache_entry_path(cache_dir: pathlib.Path, key: bytes) -> pathlib.Path:
    return cache_dir / hashlib.sha256(key).hexdigest()


def _mark_expired(path: pathlib.Path) -> None:
    expired_at = time.time() - 60
    os.utime(path, (expired_at, expired_at))


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


def test_save_sets_expiration_mtime_on_overwrite() -> None:
    """Overwriting an entry must end with the new expiration mtime, not
    the kernel-default ``st_mtime`` of an in-flight write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = pathlib.Path(tmpdir)
        cachestore = FileSystemCacheBackend(cache_dir)
        cachestore.save(b"k", b"old", expire_seconds=1)
        time.sleep(1.1)
        # The old entry is now expired; overwrite with a far-future TTL.
        cachestore.save(b"k", b"new", expire_seconds=3600)

        (entry,) = [p for p in cache_dir.iterdir() if p.is_file()]
        future_threshold = (
            datetime.now() + to_timedelta(60)
        ).timestamp()
        assert entry.stat().st_mtime >= future_threshold
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
