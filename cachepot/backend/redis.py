from typing import Optional, cast

import redis

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import ExpireSeconds, to_timedelta


class RedisCacheBackend(CacheBackendProtocol):
    redis_connection: redis.Redis

    def __init__(self, redis_connection: redis.Redis):
        self.redis = redis_connection

    def save(self, key: bytes, value: bytes, *, expire_seconds: ExpireSeconds) -> None:
        with self.redis.pipeline() as pipe:
            pipe.set(key, value)
            pipe.expire(key, to_timedelta(expire_seconds))
            pipe.execute()

    def load(self, key: bytes) -> Optional[bytes]:
        return cast(bytes, self.redis.get(key))

    def delete(self, key: bytes) -> None:
        self.redis.delete(key)
