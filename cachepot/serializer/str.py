from cachepot.serializer import SerializerProtocol


class StringSerializer(SerializerProtocol[str]):
    def serialize(self, data: str) -> bytes:
        return data.encode()

    def deserialize(self, serialized_data: bytes) -> str:
        return serialized_data.decode()
