import unittest
from dataclasses import dataclass

from cachepot.serializer.pickle import PickleSerializer


@dataclass
class A:
    x: int


class TestPickleSerializer(unittest.TestCase):
    def test_pickle_serializer(self) -> None:
        serializer = PickleSerializer()

        patterns = [
            1,
            'yes',
            str,
            int,
            A,
            A(x=100),
        ]

        for original in patterns:
            serialized = serializer.serialize(original)
            deserialized = serializer.deserialize(serialized)
            self.assertEqual(deserialized, original)
