import tempfile
import time

from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.serializer.pickle import PickleSerializer
from cachepot.serializer.str import StringSerializer
from cachepot.store import CacheStore


def test_basis() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:

        cachestore = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=1,
        )
        cachestore.put("x", 1)
        assert cachestore.get("x") == 1
        cachestore.remove("x")
        assert cachestore.get("x") is None
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3
        assert cachestore.get("y") == 3

        # expire
        time.sleep(2)
        assert cachestore.get("y") is None
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3


def test_proxy_caches_none_return_value() -> None:
    """A function whose result is ``None`` must only be executed once
    per cached call, even though ``None`` is also the sentinel the
    serializer is allowed to round-trip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )

        call_count = 0

        def returns_none() -> None:
            nonlocal call_count
            call_count += 1

        proxied = cachestore.proxy(returns_none)
        assert proxied(cache_key="none-key") is None
        assert proxied(cache_key="none-key") is None
        assert call_count == 1
