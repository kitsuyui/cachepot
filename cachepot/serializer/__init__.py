from typing import Protocol, TypeVar

T = TypeVar("T")


class SerializerProtocol(Protocol[T]):
    def serialize(self, data: T) -> bytes: ...

    def deserialize(self, serialized_data: bytes) -> T: ...
