from typing import Protocol

from cachepot.expire import Expiry

DeletedExpiredCount = int | None


class CacheBackendProtocol(Protocol):
    def save(
        self,
        key: bytes,
        value: bytes,
        *,
        expire_seconds: Expiry,
    ) -> None: ...

    def load(self, key: bytes) -> bytes | None: ...

    def exists(self, key: bytes) -> bool: ...

    def delete(self, key: bytes) -> None: ...

    def delete_expired(self) -> DeletedExpiredCount:
        """Delete expired entries and return the deleted count when known.

        Backends that delegate TTL eviction to the storage engine may return
        ``None`` when the number of expired entries is not observable.
        """
        ...
