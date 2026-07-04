import os
import pickle
import subprocess
import sys
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


def test_pickle_serializer_stabilizes_hash_randomized_sets() -> None:
    first = _serialize_frozenset_with_hash_seed("1")
    second = _serialize_frozenset_with_hash_seed("2")

    assert first == second
    assert PickleSerializer().deserialize(first) == frozenset(
        {"alpha", "bravo", "charlie"},
    )


def test_pickle_serializer_stabilizes_dict_insertion_order() -> None:
    serializer = PickleSerializer()
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 2, "a": 1}
    assert d1 == d2
    assert serializer.serialize(d1) == serializer.serialize(d2)
    assert serializer.deserialize(serializer.serialize(d1)) == d1


def _serialize_frozenset_with_hash_seed(seed: str) -> bytes:
    code = """
from cachepot.serializer.pickle import PickleSerializer

print(
    PickleSerializer()
    .serialize(frozenset({"alpha", "bravo", "charlie"}))
    .hex()
)
"""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = seed
    output = subprocess.check_output(  # noqa: S603
        [sys.executable, "-c", code],
        env=env,
        text=True,
    )
    return bytes.fromhex(output.strip())
