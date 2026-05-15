import pathlib
import sqlite3
import threading
from datetime import datetime
from types import TracebackType
from typing import cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import ExpireSeconds, to_timedelta

ConnectionLike = str | pathlib.Path | sqlite3.Connection


class SQLiteCacheBackend(CacheBackendProtocol):
    conn: sqlite3.Connection
    _lock: threading.Lock

    def __init__(self, conn: ConnectionLike) -> None:
        if isinstance(conn, (str, pathlib.Path)):
            conn = sqlite3.connect(conn, check_same_thread=False)
        self._lock = threading.Lock()
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
        expire_seconds: ExpireSeconds,
    ) -> None:
        expire_at = datetime.now() + to_timedelta(expire_seconds)
        with self._lock:
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
