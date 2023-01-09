import pathlib
import tempfile
import time

from cachepot.backend.filesystem import FileSystemCacheBackend


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


def test_expire() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = FileSystemCacheBackend(pathlib.Path(tmpdir))
        cachestore.save(b"1", b"2", expire_seconds=1)
        assert cachestore.load(b"1") == b"2"
        time.sleep(2)
        assert cachestore.load(b"1") is None
