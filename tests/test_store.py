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
