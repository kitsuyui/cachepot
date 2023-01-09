from cachepot.serializer.json import JSONSerializer


def test_json_serializer() -> None:
    serializer = JSONSerializer()

    patterns = [
        {"a": 1},
        [1, 2, 3],
        1,
        1.2,
        "something string",
        [{"something": {"nested": True}}],
        [[[[[[["yes"]]]]]]],
    ]

    for original in patterns:
        serialized = serializer.serialize(original)  # type: ignore
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original
