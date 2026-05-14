import pickle
from dataclasses import dataclass

from cachepot.serializer.pickle import PICKLE_PROTOCOL, PickleSerializer


@dataclass
class A:
    x: int


def test_pickle_serializer() -> None:
    serializer = PickleSerializer()

    patterns = [
        1,
        "yes",
        str,
        int,
        A,
        A(x=100),
    ]

    for original in patterns:
        serialized = serializer.serialize(original)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original


def test_pickle_serializer_uses_stable_protocol() -> None:
    serializer = PickleSerializer()

    assert serializer.serialize("key") == pickle.dumps(
        "key",
        protocol=PICKLE_PROTOCOL,
    )
