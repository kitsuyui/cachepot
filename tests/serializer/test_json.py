import unittest

from cachepot.serializer.json import JSONSerializer


class TestJSONSerializer(unittest.TestCase):
    def test_json_serializer(self) -> None:
        serializer = JSONSerializer()

        patterns = [
            {'a': 1},
            [1, 2, 3],
            1,
            1.2,
            'something string',
            [
                {'something': {'nested': True}}
            ],
            [[[[[[['yes']]]]]]],
        ]

        for original in patterns:
            serialized = serializer.serialize(original)  # type: ignore
            deserialized = serializer.deserialize(serialized)
            self.assertEqual(deserialized, original)
