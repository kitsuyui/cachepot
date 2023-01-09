import pickle
from typing import Any

from cachepot.serializer import SerializerProtocol


class PickleSerializer(SerializerProtocol[Any]):
    def serialize(self, data: Any) -> bytes:
        return pickle.dumps(data)

    def deserialize(self, serialized_data: bytes) -> Any:
        return pickle.loads(serialized_data)
