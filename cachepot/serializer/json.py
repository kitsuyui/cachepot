import json
from typing import Any, cast

from cachepot.serializer import SerializerProtocol

# JSONType = Union[str, int, float, Dict[str, JSONType], List[JSONType]]
# https://github.com/python/typing/issues/182
JSONType = str | int | float | dict[str, Any] | list[Any]


class JSONSerializer(SerializerProtocol[JSONType]):
    def serialize(self, data: JSONType) -> bytes:
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    def deserialize(self, serialized_data: bytes) -> JSONType:
        return cast(JSONType, json.loads(serialized_data.decode()))
