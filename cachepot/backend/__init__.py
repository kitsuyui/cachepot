from typing import Protocol

from cachepot.expire import ExpireSeconds


class CacheBackendProtocol(Protocol):
    def save(
        self,
        key: bytes,
        value: bytes,
        *,
        expire_seconds: ExpireSeconds,
    ) -> None: ...

    def load(self, key: bytes) -> bytes | None: ...

    def delete(self, key: bytes) -> None: ...

    def delete_expired(self) -> int: ...
