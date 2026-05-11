import time
from datetime import timedelta

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


def test_save_sets_ttl_atomically() -> None:
    """``SET`` and the TTL must be applied in one command; a server-side
    failure between SET and EXPIRE used to leak persistent keys."""
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    cachestore.save(b"ttl-check", b"value", expire_seconds=60)
    try:
        # ``TTL`` returns -1 for "no TTL" and -2 for "no key". A correct
        # implementation always lands somewhere in (0, 60].
        ttl = r.ttl(b"ttl-check")
        assert 0 < ttl <= 60
    finally:
        cachestore.delete(b"ttl-check")


def test_save_accepts_timedelta_expire_seconds() -> None:
    """The backend should still honour ``timedelta`` inputs from
    ``ExpireSeconds`` after the SET+EX consolidation."""
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    cachestore.save(b"td-key", b"v", expire_seconds=timedelta(seconds=30))
    try:
        ttl = r.ttl(b"td-key")
        assert 0 < ttl <= 30
        assert cachestore.load(b"td-key") == b"v"
    finally:
        cachestore.delete(b"td-key")
