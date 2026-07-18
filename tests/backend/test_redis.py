import time
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
import redis

from cachepot.backend import CacheEntryTooLargeError
from cachepot.backend.redis import RedisCacheBackend


def test_various_connection_like() -> None:
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    assert cachestore.redis is r
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


def test_delete_expired_is_noop() -> None:
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    assert cachestore.delete_expired() is None


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


def test_exists() -> None:
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    assert not cachestore.exists(b"exists-key")
    cachestore.save(b"exists-key", b"v", expire_seconds=60)
    assert cachestore.exists(b"exists-key")
    cachestore.delete(b"exists-key")
    assert not cachestore.exists(b"exists-key")


def test_exists_does_not_return_true_for_expired() -> None:
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    cachestore.save(b"exists-expire-key", b"v", expire_seconds=1)
    assert cachestore.exists(b"exists-expire-key")
    time.sleep(2)
    assert not cachestore.exists(b"exists-expire-key")


def test_save_accepts_timedelta_expire_seconds() -> None:
    """The backend should still honour ``timedelta`` inputs from
    ``Expiry`` after the SET+EX consolidation."""
    r = redis.Redis(host="localhost", port=6379, db=0)
    cachestore = RedisCacheBackend(r)
    cachestore.save(b"td-key", b"v", expire_seconds=timedelta(seconds=30))
    try:
        ttl = r.ttl(b"td-key")
        assert 0 < ttl <= 30
        assert cachestore.load(b"td-key") == b"v"
    finally:
        cachestore.delete(b"td-key")


def test_save_zero_expire_skips_write() -> None:
    """expire_seconds=0 must not raise a ResponseError.

    Redis rejects EX=0 at the server level.  The backend handles this by
    skipping the write entirely — the result is the same as an immediately
    expired entry: load() returns None, matching FileSystem and SQLite
    backend behaviour.
    """
    mock_redis = MagicMock()
    mock_redis.strlen.return_value = 0
    mock_redis.get.return_value = None
    cachestore = RedisCacheBackend(mock_redis)

    cachestore.save(b"key", b"value", expire_seconds=0)

    mock_redis.set.assert_not_called()
    assert cachestore.load(b"key") is None


def test_save_rejects_entries_larger_than_max_entry_bytes() -> None:
    mock_redis = MagicMock()
    cachestore = RedisCacheBackend(mock_redis, max_entry_bytes=3)

    with pytest.raises(CacheEntryTooLargeError, match="save"):
        cachestore.save(b"key", b"toolarge", expire_seconds=60)

    mock_redis.set.assert_not_called()


def test_load_rejects_entries_larger_than_max_entry_bytes() -> None:
    mock_redis = MagicMock()
    mock_redis.strlen.return_value = 8
    cachestore = RedisCacheBackend(mock_redis, max_entry_bytes=3)

    with pytest.raises(CacheEntryTooLargeError, match="load"):
        cachestore.load(b"key")

    mock_redis.get.assert_not_called()
