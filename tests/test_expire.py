import unittest
from datetime import timedelta

from cachepot.expire import to_timedelta


class TestExpireSeconds(unittest.TestCase):

    def test_to_timedelta(self) -> None:
        # float
        self.assertEqual(to_timedelta(1.0), timedelta(seconds=1.0))

        # int
        self.assertEqual(to_timedelta(3), timedelta(seconds=3))

        # timedelta
        self.assertEqual(timedelta(days=5), timedelta(days=5))
