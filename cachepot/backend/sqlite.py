import pathlib
import sqlite3
import threading
from datetime import datetime
from types import TracebackType
from typing import cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import Expiry, to_timedelta

ConnectionLike = str | pathlib.Path | sqlite3.Connection


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.text_factory = bytes
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

    def __init__(self, conn: ConnectionLike) -> None:
        if isinstance(conn, (str, pathlib.Path)):
            conn = _open_and_init(conn)
        else:
            _init_schema(conn)
        self._lock = threading.Lock()
        self.conn = conn

    def close(self) -> None:
        with self._lock:
            self.conn.close()

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
            expire_at = datetime.now() + to_timedelta(expire_seconds)
            self.conn.execute(
                """\
INSERT OR REPLACE INTO cachepot
            (key, value, expire_at)
     VALUES (?, ?, ?)""",
                (key, value, expire_at),
            )
            self.conn.commit()

    def load(self, key: bytes) -> bytes | None:
        current_datetime = datetime.now()
        with self._lock:
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
        current_datetime = datetime.now()
        with self._lock:
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
            cur = self.conn.execute(
                """\
        DELETE
          FROM cachepot
         WHERE expire_at <= ?""",
                (datetime.now(),),
            )
            self.conn.commit()
        return cur.rowcount
