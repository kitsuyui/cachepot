from types import TracebackType
from typing import cast

from redis import Redis

from cachepot.backend import CacheBackendProtocol, DeletedExpiredCount
from cachepot.expire import Expiry, to_timedelta


class RedisCacheBackend(CacheBackendProtocol):
    redis: Redis

    def __init__(self, redis_connection: Redis) -> None:
        self.redis = redis_connection

    def save(
        self,
        key: bytes,
        value: bytes,
        *,
        expire_seconds: Expiry,
    ) -> None:
        # ``SET key value EX seconds`` is a single Redis command, so the
        # value and its TTL land together. The previous pipeline form
        # could leave the key without a TTL if EXPIRE failed after SET.
        td = to_timedelta(expire_seconds)
        if td.total_seconds() == 0:
            # Redis rejects EX=0. A zero-second TTL means the entry expires
            # immediately; skip the write so load() returns None, matching
            # FileSystem and SQLite backend behaviour.
            return
        self.redis.set(key, value, ex=td)

    def load(self, key: bytes) -> bytes | None:
        return cast(bytes, self.redis.get(key))

    def exists(self, key: bytes) -> bool:
        return bool(self.redis.exists(key))

    def delete(self, key: bytes) -> None:
        self.redis.delete(key)

    def delete_expired(self) -> DeletedExpiredCount:
        """Return ``None`` because Redis expires entries server-side.

        Redis does not expose an API to enumerate or count entries that have
        already been evicted by their TTL.  This method is a no-op that
        satisfies the ``CacheBackendProtocol`` contract; the actual expiry is
        handled transparently by Redis.  Callers must treat ``None`` as an
        unknown deleted-entry count, not as zero expired entries.
        """
        return None

    def close(self) -> None:
        self.redis.close()

    def __enter__(self) -> "RedisCacheBackend":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()
