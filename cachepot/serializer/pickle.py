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


class _DeterministicPickler(_PicklerBase):
    dispatch = _PicklerBase.dispatch.copy()

    @staticmethod
    def _sorted_items(data: set[Any] | frozenset[Any]) -> list[Any]:
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
        Consider :class:`cachepot.serializer.json.JsonSerializer` or
        :class:`cachepot.serializer.msgpack.MsgpackSerializer` for
        untrusted environments.
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
