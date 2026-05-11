import pathlib
import tempfile
import time
from datetime import datetime

from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.expire import to_timedelta


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
