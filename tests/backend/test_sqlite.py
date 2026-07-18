import concurrent.futures
import pathlib
import sqlite3
import tempfile
import time
import unittest.mock
from datetime import datetime, timedelta, timezone

import pytest

import cachepot.backend.sqlite as sqlite_backend
from cachepot.backend import CacheEntryTooLargeError
from cachepot.backend.sqlite import SQLiteCacheBackend

_CONTROLLED_CURRENT_TIME: list[datetime] = [datetime(1970, 1, 1)]
_CONTROLLED_LOCK_TIME: list[datetime] = [datetime(1970, 1, 1)]


class _ControlledDateTime:
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        dt = _CONTROLLED_CURRENT_TIME[0]
        if tz is not None:
            return dt.replace(tzinfo=tz)
        return dt


class _AdvancingLock:
    def __enter__(self):
        _CONTROLLED_CURRENT_TIME[0] = _CONTROLLED_LOCK_TIME[0]
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return None


def test_schema_version_is_set_on_new_database() -> None:
    """A freshly initialised database must have user_version = 1."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        conn = sqlite3.connect(f.name)
        SQLiteCacheBackend(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        conn.close()


def test_schema_version_upgrades_unversioned_database() -> None:
    """An existing database with user_version = 0 is accepted and upgraded
    to version 1 without requiring a data migration."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        # Simulate a pre-versioning database: create the schema manually,
        # leave user_version at the SQLite default of 0.
        conn = sqlite3.connect(f.name)
        conn.execute(
            "CREATE TABLE cachepot"
            " (key BLOB PRIMARY KEY, value BLOB, expire_at timestamp)",
        )
        conn.commit()
        conn.close()

        # Opening with SQLiteCacheBackend must succeed and migrate
        # user_version to 1.
        with SQLiteCacheBackend(f.name) as backend:
            backend.save(b"k", b"v", expire_seconds=60)
            assert backend.load(b"k") == b"v"

        conn2 = sqlite3.connect(f.name)
        version = conn2.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        conn2.close()


def test_schema_version_raises_on_future_schema() -> None:
    """Opening a database whose user_version exceeds the current library
    version must raise RuntimeError rather than silently misinterpreting it."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        conn = sqlite3.connect(f.name)
        conn.execute("PRAGMA user_version = 999")
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="schema version 999"):
            SQLiteCacheBackend(f.name)


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


def test_sqlite_connection_text_factory_is_preserved() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE external (value TEXT)")
    conn.execute("INSERT INTO external (value) VALUES (?)", ("alpha",))

    cachestore = SQLiteCacheBackend(conn)
    cachestore.save(b"key", b"value", expire_seconds=1)

    assert conn.text_factory is str
    assert conn.execute("SELECT value FROM external").fetchone() == ("alpha",)
    assert cachestore.load(b"key") == b"value"


def test_sqlite_close_closes_connection() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"1", b"2", expire_seconds=1)
        cachestore.close()

        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.load(b"1")


def test_sqlite_context_manager_closes_connection() -> None:
    with tempfile.NamedTemporaryFile() as f:
        with SQLiteCacheBackend(f.name) as cachestore:
            cachestore.save(b"1", b"2", expire_seconds=1)
            assert cachestore.load(b"1") == b"2"

        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.load(b"1")


def test_use_after_close_raises_runtime_error() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"k", b"v", expire_seconds=60)
        cachestore.close()

        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.save(b"k2", b"v2", expire_seconds=60)
        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.load(b"k")
        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.exists(b"k")
        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.delete(b"k")
        with pytest.raises(RuntimeError, match="already closed"):
            cachestore.delete_expired()


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


def test_exists() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        assert not cachestore.exists(b"k")
        cachestore.save(b"k", b"v", expire_seconds=60)
        assert cachestore.exists(b"k")
        cachestore.delete(b"k")
        assert not cachestore.exists(b"k")


def test_exists_does_not_return_true_for_expired() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name)
        cachestore.save(b"k", b"v", expire_seconds=1)
        assert cachestore.exists(b"k")
        time.sleep(2)
        assert not cachestore.exists(b"k")


def test_save_rejects_entries_larger_than_max_entry_bytes() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name, max_entry_bytes=3)

        with pytest.raises(CacheEntryTooLargeError, match="save"):
            cachestore.save(b"k", b"toolarge", expire_seconds=60)


def test_load_rejects_entries_larger_than_max_entry_bytes() -> None:
    with tempfile.NamedTemporaryFile() as f:
        cachestore = SQLiteCacheBackend(f.name, max_entry_bytes=3)
        cachestore.conn.execute(
            """\
INSERT INTO cachepot
            (key, value, expire_at)
     VALUES (?, ?, ?)""",
            (
                b"k",
                b"toolarge",
                (
                    datetime.now(timezone.utc) + timedelta(seconds=60)
                ).isoformat(),
            ),
        )
        cachestore.conn.commit()

        with pytest.raises(CacheEntryTooLargeError, match="load"):
            cachestore.load(b"k")


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


def test_init_closes_internal_connection_on_execute_failure() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = f.name

    spy_holder: list[unittest.mock.MagicMock] = []
    real_connect = sqlite3.connect

    def patched_connect(
        path: object, **kwargs: object,
    ) -> sqlite3.Connection:
        real_conn = real_connect(path, **kwargs)  # type: ignore[call-overload]
        spy = unittest.mock.MagicMock(wraps=real_conn)
        spy.execute.side_effect = sqlite3.OperationalError("injected")
        spy_holder.append(spy)
        return spy

    with (
        unittest.mock.patch("sqlite3.connect", side_effect=patched_connect),
        pytest.raises(sqlite3.OperationalError, match="injected"),
    ):
        SQLiteCacheBackend(db_path)

    spy_holder[0].close.assert_called_once()


def test_init_does_not_close_caller_connection_on_failure() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        real_conn = sqlite3.connect(f.name)
        spy = unittest.mock.MagicMock(wraps=real_conn)
        spy.execute.side_effect = sqlite3.OperationalError("injected")

        with pytest.raises(sqlite3.OperationalError, match="injected"):
            SQLiteCacheBackend(spy)

        spy.close.assert_not_called()
        real_conn.close()
