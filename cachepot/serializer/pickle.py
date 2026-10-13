import io
import pickle
import sys
import warnings
from itertools import islice
from typing import Any

from cachepot._warnings import CachepotWarning
from cachepot.serializer import SerializerProtocol

PICKLE_PROTOCOL = 4
_PicklerBase: Any = pickle._Pickler  # type: ignore[attr-defined]

# Deterministic ordering sorts by each element's own pickled bytes, so the
# full container is copied into a sorted list and every element (or, for
# dicts, every key) is re-pickled into a standalone sort key. Serializing a
# container above this size temporarily holds several multiples of its data
# in memory; see ``_warn_if_large_container``.
_LARGE_CONTAINER_WARN_THRESHOLD = 10_000


def _warn_if_large_container(size: int, kind: str) -> None:
    if size > _LARGE_CONTAINER_WARN_THRESHOLD:
        warnings.warn(
            f"PickleSerializer is serializing a {kind} with {size} "
            f"elements (> {_LARGE_CONTAINER_WARN_THRESHOLD}). Deterministic "
            "ordering requires a full sorted copy and a re-pickled sort key "
            "per element, so peak memory during serialize() can be several "
            "times the size of the data itself.",
            CachepotWarning,
            stacklevel=3,
        )


class _DeterministicPickler(_PicklerBase):
    dispatch = _PicklerBase.dispatch.copy()

    @staticmethod
    def _sorted_items(data: set[Any] | frozenset[Any]) -> list[Any]:
        _warn_if_large_container(len(data), "set/frozenset")
        return sorted(data, key=_stable_pickle_sort_key)

    def save_set(self, obj: set[Any]) -> None:  # noqa: C901
        if self.proto < 4:
            self.save_reduce(set, (self._sorted_items(obj),), obj=obj)
            return

        self.write(pickle.EMPTY_SET)
        self.memoize(obj)

        items = iter(self._sorted_items(obj))
        while True:
            batch = list(islice(items, self._BATCHSIZE))
            if batch:
                self.write(pickle.MARK)
                for item in batch:
                    self.save(item)
                self.write(pickle.ADDITEMS)
            if len(batch) < self._BATCHSIZE:
                return

    def save_frozenset(self, obj: frozenset[Any]) -> None:  # noqa: C901
        if self.proto < 4:
            self.save_reduce(frozenset, (self._sorted_items(obj),), obj=obj)
            return

        self.write(pickle.MARK)
        for item in self._sorted_items(obj):
            self.save(item)

        if id(obj) in self.memo:
            self.write(pickle.POP_MARK + self.get(self.memo[id(obj)][0]))
            return

        self.write(pickle.FROZENSET)
        self.memoize(obj)

    def save_dict(self, obj: dict[Any, Any]) -> None:  # noqa: C901
        if self.bin:
            self.write(pickle.EMPTY_DICT)
        else:
            self.write(pickle.MARK + pickle.DICT)
        self.memoize(obj)
        _warn_if_large_container(len(obj), "dict")
        sorted_items = sorted(
            obj.items(), key=lambda kv: _stable_pickle_sort_key(kv[0]),
        )
        if sys.version_info >= (3, 14):
            # Python 3.14 changed the private signature of
            # ``_Pickler._batch_setitems`` to take the source object as a
            # second positional argument.
            self._batch_setitems(iter(sorted_items), obj)
        else:
            self._batch_setitems(iter(sorted_items))


_DeterministicPickler.dispatch[set] = _DeterministicPickler.save_set
_DeterministicPickler.dispatch[frozenset] = (
    _DeterministicPickler.save_frozenset
)
_DeterministicPickler.dispatch[dict] = _DeterministicPickler.save_dict


def _stable_pickle_sort_key(data: Any) -> bytes:
    return _pickle_dumps(data)


def _pickle_dumps(data: Any) -> bytes:
    stream = io.BytesIO()
    _DeterministicPickler(stream, protocol=PICKLE_PROTOCOL).dump(data)
    return stream.getvalue()


class PickleSerializer(SerializerProtocol[Any]):
    """Pickle-based serializer.

    Warning:
        ``pickle`` can execute arbitrary code during deserialization.
        Only use this serializer with cache backends whose storage you fully
        control and trust. Never deserialize data received from untrusted
        sources (e.g. shared caches, user-supplied input).
        Consider :class:`cachepot.serializer.json.JSONSerializer` for
        untrusted environments.

    Warning:
        Serializing a ``set``, ``frozenset``, or ``dict`` requires making
        its output byte-for-byte deterministic. To do that, ``serialize()``
        copies the container into a sorted list and re-pickles every
        element (every key, for ``dict``) into a standalone sort key, so
        peak memory usage can be several times the size of the data. A
        :class:`~cachepot._warnings.CachepotWarning` is emitted when a
        container exceeds ``_LARGE_CONTAINER_WARN_THRESHOLD`` elements.
    """

    def __init__(self) -> None:
        warnings.warn(
            "PickleSerializer can execute arbitrary code during "
            "deserialization. Use it only with trusted cache data.",
            CachepotWarning,
            stacklevel=2,
        )

    def serialize(self, data: Any) -> bytes:
        return _pickle_dumps(data)

    def deserialize(self, serialized_data: bytes) -> Any:
        """Deserialize bytes produced by :meth:`serialize`.

        Warning:
            Calls ``pickle.loads``, which can execute arbitrary code.
            Only pass data from trusted sources.
        """
        return pickle.loads(serialized_data)  # noqa: S301
