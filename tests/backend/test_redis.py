import time

import redis

from cachepot.backend.redis import RedisCacheBackend


def test_various_connection_like() -> None:
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    assert cachestore.load(b"1") is None
    cachestore.save(b"1", b"2", expire_seconds=1)
    assert cachestore.load(b"1") == b"2"
    cachestore.delete(b"1")
    assert cachestore.load(b"1") is None


def test_expire() -> None:
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    cachestore.save(b"1", b"2", expire_seconds=1)
    assert cachestore.load(b"1") == b"2"
    time.sleep(2)
    assert cachestore.load(b"1") is None
