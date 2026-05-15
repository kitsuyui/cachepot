import concurrent.futures
import pathlib
import sqlite3
import tempfile
import time

import pytest

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


def test_sqlite_close_closes_connection() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"1", b"2", expire_seconds=1)
        cachestore.close()

        with pytest.raises(sqlite3.ProgrammingError):
            cachestore.load(b"1")


def test_sqlite_context_manager_closes_connection() -> None:
    with tempfile.NamedTemporaryFile() as f:
        with SQLiteCacheBackend(f.name) as cachestore:
            cachestore.save(b"1", b"2", expire_seconds=1)
            assert cachestore.load(b"1") == b"2"

        with pytest.raises(sqlite3.ProgrammingError):
            cachestore.load(b"1")


def test_expire() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"1", b"2", expire_seconds=1)
        assert cachestore.load(b"1") == b"2"
        time.sleep(2)
        assert cachestore.load(b"1") is None


def test_delete_expired() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"expired", b"value", expire_seconds=1)
        cachestore.save(b"live", b"value", expire_seconds=60)

        time.sleep(2)

        # expired row is filtered by load() but still physically present
        assert cachestore.load(b"expired") is None
        assert cachestore.load(b"live") == b"value"

        deleted = cachestore.delete_expired()
        assert deleted == 1

        # live row is unaffected
        assert cachestore.load(b"live") == b"value"

        # calling again with nothing expired returns 0
        assert cachestore.delete_expired() == 0


def _thread_worker(cachestore: SQLiteCacheBackend, i: int) -> None:
    key = str(i).encode()
    cachestore.save(key, key, expire_seconds=10)
    assert cachestore.load(key) == key
    cachestore.delete(key)


def test_sqlite_thread_safe() -> None:
    import functools

    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        worker = functools.partial(_thread_worker, cachestore)
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        with pool as executor:
            futures = [executor.submit(worker, i) for i in range(32)]
        results = [fut.result() for fut in futures]
    assert results == [None] * 32
