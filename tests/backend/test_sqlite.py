import concurrent.futures
import pathlib
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta

import pytest

import cachepot.backend.sqlite as sqlite_backend
from cachepot.backend.sqlite import SQLiteCacheBackend

_CONTROLLED_CURRENT_TIME: list[datetime] = [datetime(1970, 1, 1)]
_CONTROLLED_LOCK_TIME: list[datetime] = [datetime(1970, 1, 1)]


class _ControlledDateTime:
    @classmethod
    def now(cls):
        return _CONTROLLED_CURRENT_TIME[0]


class _AdvancingLock:
    def __enter__(self):
        _CONTROLLED_CURRENT_TIME[0] = _CONTROLLED_LOCK_TIME[0]
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return None


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


def test_save_expiration_starts_after_lock_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 1, 1, 0, 0, 0)
    _CONTROLLED_CURRENT_TIME[0] = start
    _CONTROLLED_LOCK_TIME[0] = start + timedelta(seconds=11)

    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        monkeypatch.setattr(sqlite_backend, "datetime", _ControlledDateTime)
        monkeypatch.setattr(cachestore, "_lock", _AdvancingLock())

        cachestore.save(b"delayed", b"value", expire_seconds=10)

        assert cachestore.load(b"delayed") == b"value"


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
