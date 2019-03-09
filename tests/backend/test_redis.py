import time
import unittest

import redis

from cachepot.backend.redis import RedisCacheBackend


class TestRedisCacheBackend(unittest.TestCase):

    def test_various_connection_like(self) -> None:
        r = redis.Redis(host='localhost', port=6379, db=0)
        cachestore = RedisCacheBackend(r)
        self.assertEqual(cachestore.load(b'1'), None)
        cachestore.save(b'1', b'2', expire_seconds=1)
        self.assertEqual(cachestore.load(b'1'), b'2')
        cachestore.delete(b'1')
        self.assertEqual(cachestore.load(b'1'), None)

    def test_expire(self) -> None:
        r = redis.Redis(host='localhost', port=6379, db=0)
        cachestore = RedisCacheBackend(r)
        cachestore.save(b'1', b'2', expire_seconds=1)
        self.assertEqual(cachestore.load(b'1'), b'2')
        time.sleep(2)
        self.assertEqual(cachestore.load(b'1'), None)
