import tempfile
import time
import unittest

from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.serializer.pickle import PickleSerializer
from cachepot.serializer.str import StringSerializer
from cachepot.store import CacheStore


class TestCacheStore(unittest.TestCase):

    def test_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:

            cachestore = CacheStore(
                namespace='testing',
                key_serializer=StringSerializer(),
                value_serializer=PickleSerializer(),
                backend=FileSystemCacheBackend(tmpdir),
                default_expire_seconds=1,
            )
            cachestore.put('x', 1)
            self.assertEqual(cachestore.get('x'), 1)
            cachestore.remove('x')
            self.assertEqual(cachestore.get('x'), None)
            self.assertEqual(cachestore.proxy(lambda: 3)(cache_key='y'), 3)
            self.assertEqual(cachestore.proxy(lambda: 3)(cache_key='y'), 3)
            self.assertEqual(cachestore.get('y'), 3)

            # expire
            time.sleep(2)
            self.assertEqual(cachestore.get('y'), None)
            self.assertEqual(cachestore.proxy(lambda: 3)(cache_key='y'), 3)
