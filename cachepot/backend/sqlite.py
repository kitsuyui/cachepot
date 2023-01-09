import pathlib
import sqlite3
from datetime import datetime
from typing import Optional, Union, cast

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import ExpireSeconds, to_timedelta

ConnectionLike = Union[str, pathlib.Path, sqlite3.Connection]


class SQLiteCacheBackend(CacheBackendProtocol):
    conn: sqlite3.Connection

    def __init__(self, conn: ConnectionLike):
        if isinstance(conn, str):
            conn = sqlite3.connect(conn)
        elif isinstance(conn, pathlib.Path):
            conn = sqlite3.connect(conn)
        conn.text_factory = bytes
        conn.execute(
            """\
CREATE TABLE IF NOT EXISTS cachepot
           ( key BLOB PRIMARY KEY
           , value BLOB
           , expire_at timestamp
           )"""
        )
        conn.execute(
            """\
CREATE UNIQUE INDEX IF NOT EXISTS idx_cachepot
                 ON cachepot
                  ( key
                  , expire_at
                  )"""
        )
        self.conn = conn

    def save(self, key: bytes, value: bytes, *, expire_seconds: ExpireSeconds) -> None:
        expire_at = datetime.now() + to_timedelta(expire_seconds)
        self.conn.execute(
            """\
INSERT OR REPLACE INTO cachepot
            (key, value, expire_at)
     VALUES (?, ?, ?)""",
            (key, value, expire_at),
        )
        self.conn.commit()

    def load(self, key: bytes) -> Optional[bytes]:
        current_datetime = datetime.now()
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
        self.conn.execute(
            """\
        DELETE
          FROM cachepot
         WHERE key = ?""",
            (key,),
        )
        self.conn.commit()
