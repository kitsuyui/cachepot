import pickle
from typing import Any

from cachepot.serializer import SerializerProtocol

PICKLE_PROTOCOL = 4


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

    def serialize(self, data: Any) -> bytes:
        return pickle.dumps(data, protocol=PICKLE_PROTOCOL)

    def deserialize(self, serialized_data: bytes) -> Any:
        """Deserialize bytes produced by :meth:`serialize`.

        Warning:
            Calls ``pickle.loads``, which can execute arbitrary code.
            Only pass data from trusted sources.
        """
        return pickle.loads(serialized_data)  # noqa: S301
