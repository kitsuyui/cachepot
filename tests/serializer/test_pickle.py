import os
import pickle
import subprocess
import sys
import warnings
from dataclasses import dataclass

import pytest

from cachepot._warnings import CachepotWarning
from cachepot.serializer.pickle import (
    _LARGE_CONTAINER_WARN_THRESHOLD,
    PICKLE_PROTOCOL,
    PickleSerializer,
)


@dataclass
class A:
    x: int


def _new_pickle_serializer() -> PickleSerializer:
    with pytest.warns(CachepotWarning):
        return PickleSerializer()


def test_pickle_serializer() -> None:
    serializer = _new_pickle_serializer()

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
    serializer = _new_pickle_serializer()

    assert serializer.serialize("key") == pickle.dumps(
        "key",
        protocol=PICKLE_PROTOCOL,
    )


def test_pickle_serializer_stabilizes_hash_randomized_sets() -> None:
    first = _serialize_frozenset_with_hash_seed("1")
    second = _serialize_frozenset_with_hash_seed("2")

    assert first == second
    assert _new_pickle_serializer().deserialize(first) == frozenset(
        {"alpha", "bravo", "charlie"},
    )


def test_pickle_serializer_stabilizes_dict_insertion_order() -> None:
    serializer = _new_pickle_serializer()
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 2, "a": 1}
    assert d1 == d2
    assert serializer.serialize(d1) == serializer.serialize(d2)
    assert serializer.deserialize(serializer.serialize(d1)) == d1


def test_pickle_serializer_warns_on_large_set() -> None:
    serializer = _new_pickle_serializer()
    large = frozenset(range(_LARGE_CONTAINER_WARN_THRESHOLD + 1))

    with pytest.warns(CachepotWarning, match="set/frozenset"):
        serializer.serialize(large)


def test_pickle_serializer_warns_on_large_dict() -> None:
    serializer = _new_pickle_serializer()
    large = {i: i for i in range(_LARGE_CONTAINER_WARN_THRESHOLD + 1)}

    with pytest.warns(CachepotWarning, match="dict"):
        serializer.serialize(large)


def test_pickle_serializer_does_not_warn_on_small_containers() -> None:
    serializer = _new_pickle_serializer()

    with warnings.catch_warnings():
        warnings.simplefilter("error", category=CachepotWarning)
        serializer.serialize(frozenset({1, 2, 3}))
        serializer.serialize({"a": 1, "b": 2})


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
