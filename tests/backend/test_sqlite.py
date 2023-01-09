import pathlib
import tempfile
import time

from cachepot.backend.sqlite import SQLiteCacheBackend


def test_sqlite_connection() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(pathlib.Path(f.name))
        assert cachestore.load(b"1") is None
        cachestore.save(b"1", b"2", expire_seconds=1)
        assert cachestore.load(b"1") == b"2"
        cachestore.delete(b"1")
        assert cachestore.load(b"1") is None

    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        assert cachestore.load(b"3") is None
        cachestore.save(b"3", b"4", expire_seconds=1)
        assert cachestore.load(b"3") == b"4"
        cachestore.delete(b"3")
        assert cachestore.load(b"3") is None


def test_expire() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"1", b"2", expire_seconds=1)
        assert cachestore.load(b"1") == b"2"
        time.sleep(2)
        assert cachestore.load(b"1") is None
