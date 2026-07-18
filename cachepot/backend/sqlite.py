import pathlib
import sqlite3
import threading
from datetime import datetime, timezone
from types import TracebackType
from typing import cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import Expiry, to_timedelta

ConnectionLike = str | pathlib.Path | sqlite3.Connection

_SCHEMA_VERSION = 2
_AUTOMATIC_EXPIRED_CLEANUP_INTERVAL = to_timedelta(60)


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cachepot_expire_at "
        "ON cachepot(expire_at)",
    )


def _raise_for_future_schema(from_version: int) -> None:
    if from_version > _SCHEMA_VERSION:
        raise RuntimeError(
            f"cachepot database schema version {from_version} is newer than "
            f"the current library version ({_SCHEMA_VERSION}). "
            "Upgrade cachepot to open this database.",
        )


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    _raise_for_future_schema(from_version)
    if from_version < 2:
        _migrate_to_v2(conn)
    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    conn.commit()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """\
CREATE TABLE IF NOT EXISTS cachepot
           ( key BLOB PRIMARY KEY
           , value BLOB
           , expire_at timestamp
           )""",
    )
    conn.execute("DROP INDEX IF EXISTS idx_cachepot")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != _SCHEMA_VERSION:
        _migrate(conn, version)


def _open_and_init(path: str | pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        _init_schema(conn)
    except Exception:
        conn.close()
        raise
    return conn


class SQLiteCacheBackend(CacheBackendProtocol):
    conn: sqlite3.Connection
    _lock: threading.Lock
    _closed: bool
    _next_expired_cleanup_at: datetime | None

    def __init__(self, conn: ConnectionLike) -> None:
        if isinstance(conn, (str, pathlib.Path)):
            conn = _open_and_init(conn)
        else:
            _init_schema(conn)
        self._lock = threading.Lock()
        self.conn = conn
        self._closed = False
        self._next_expired_cleanup_at = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self.conn.close()

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLiteCacheBackend is already closed")

    def __enter__(self) -> "SQLiteCacheBackend":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def save(
        self,
        key: bytes,
        value: bytes,
        *,
        expire_seconds: Expiry,
    ) -> None:
        with self._lock:
            self._check_open()
            current_datetime = datetime.now(timezone.utc)
            self._maybe_delete_expired_locked(current_datetime)
            expire_at = (
                current_datetime + to_timedelta(expire_seconds)
            ).isoformat()
            self.conn.execute(
                """\
INSERT OR REPLACE INTO cachepot
            (key, value, expire_at)
     VALUES (?, ?, ?)""",
                (key, value, expire_at),
            )
            self.conn.commit()

    def _maybe_delete_expired_locked(self, current_datetime: datetime) -> None:
        if (
            self._next_expired_cleanup_at is not None
            and current_datetime < self._next_expired_cleanup_at
        ):
            return
        self._delete_expired_locked(current_datetime)
        self._next_expired_cleanup_at = (
            current_datetime + _AUTOMATIC_EXPIRED_CLEANUP_INTERVAL
        )

    def _delete_expired_locked(
        self,
        current_datetime: datetime,
    ) -> sqlite3.Cursor:
        return self.conn.execute(
            """\
        DELETE
          FROM cachepot
         WHERE expire_at <= ?""",
            (current_datetime.isoformat(),),
        )

    def load(self, key: bytes) -> bytes | None:
        with self._lock:
            self._check_open()
            current_datetime = datetime.now(timezone.utc).isoformat()
            result = self.conn.execute(
                """\
        SELECT value
          FROM cachepot
         WHERE key = ?
           AND expire_at > ?""",
                (key, current_datetime),
            ).fetchone()
        if result:
            return cast(bytes, result[0])
        return None

    def exists(self, key: bytes) -> bool:
        with self._lock:
            self._check_open()
            current_datetime = datetime.now(timezone.utc).isoformat()
            result = self.conn.execute(
                """\
        SELECT 1
          FROM cachepot
         WHERE key = ?
           AND expire_at > ?""",
                (key, current_datetime),
            ).fetchone()
        return result is not None

    def delete(self, key: bytes) -> None:
        with self._lock:
            self._check_open()
            self.conn.execute(
                """\
        DELETE
          FROM cachepot
         WHERE key = ?""",
                (key,),
            )
            self.conn.commit()

    def delete_expired(self) -> int:
        """Delete all expired rows and return the number of deleted rows."""
        with self._lock:
            self._check_open()
            cur = self._delete_expired_locked(datetime.now(timezone.utc))
            self.conn.commit()
        return cur.rowcount
