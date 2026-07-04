import pathlib
import sqlite3
import threading
from datetime import datetime, timezone
from types import TracebackType
from typing import cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import Expiry, to_timedelta

ConnectionLike = str | pathlib.Path | sqlite3.Connection

_SCHEMA_VERSION = 1


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    if from_version > _SCHEMA_VERSION:
        raise RuntimeError(
            f"cachepot database schema version {from_version} is newer than "
            f"the current library version ({_SCHEMA_VERSION}). "
            "Upgrade cachepot to open this database.",
        )
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
    conn.execute(
        """\
CREATE UNIQUE INDEX IF NOT EXISTS idx_cachepot
                 ON cachepot
                  ( key
                  , expire_at
                  )""",
    )
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

    def __init__(self, conn: ConnectionLike) -> None:
        if isinstance(conn, (str, pathlib.Path)):
            conn = _open_and_init(conn)
        else:
            _init_schema(conn)
        self._lock = threading.Lock()
        self.conn = conn
        self._closed = False

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
            expire_at = (
                datetime.now(timezone.utc) + to_timedelta(expire_seconds)
            ).isoformat()
            self.conn.execute(
                """\
INSERT OR REPLACE INTO cachepot
            (key, value, expire_at)
     VALUES (?, ?, ?)""",
                (key, value, expire_at),
            )
            self.conn.commit()

    def load(self, key: bytes) -> bytes | None:
        current_datetime = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._check_open()
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
        current_datetime = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._check_open()
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
            cur = self.conn.execute(
                """\
        DELETE
          FROM cachepot
         WHERE expire_at <= ?""",
                (datetime.now(timezone.utc).isoformat(),),
            )
            self.conn.commit()
        return cur.rowcount
