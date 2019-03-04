import pathlib
import tempfile
import time
import unittest

from cachepot.backend.filesystem import FileSystemCacheBackend


class TestFileSystemCacheBackend(unittest.TestCase):

    def test_various_pathlike(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cachestore = FileSystemCacheBackend(pathlib.Path(tmpdir))
            self.assertEqual(cachestore.load(b'1'), None)
            cachestore.save(b'1', b'2', expire_seconds=1)
            self.assertEqual(cachestore.load(b'1'), b'2')
            cachestore.delete(b'1')
            self.assertEqual(cachestore.load(b'1'), None)

        with tempfile.TemporaryDirectory() as tmpdir:
            cachestore = FileSystemCacheBackend(tmpdir)
            self.assertEqual(cachestore.load(b'3'), None)
            cachestore.save(b'3', b'4', expire_seconds=1)
            self.assertEqual(cachestore.load(b'3'), b'4')
            cachestore.delete(b'3')
            self.assertEqual(cachestore.load(b'3'), None)

    def test_expire(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cachestore = FileSystemCacheBackend(pathlib.Path(tmpdir))
            cachestore.save(b'1', b'2', expire_seconds=1)
            self.assertEqual(cachestore.load(b'1'), b'2')
            time.sleep(2)
            self.assertEqual(cachestore.load(b'1'), None)
