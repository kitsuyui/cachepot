from typing import cast

from redis import Redis

from cachepot.backend import CacheBackendProtocol
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
        self.redis.set(key, value, ex=to_timedelta(expire_seconds))

    def load(self, key: bytes) -> bytes | None:
        return cast(bytes, self.redis.get(key))

    def exists(self, key: bytes) -> bool:
        return bool(self.redis.exists(key))

    def delete(self, key: bytes) -> None:
        self.redis.delete(key)

    def delete_expired(self) -> int:
        return 0
