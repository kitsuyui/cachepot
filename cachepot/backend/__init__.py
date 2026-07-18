from types import TracebackType
from typing import Protocol

from cachepot.expire import Expiry

DeletedExpiredCount = int | None
DEFAULT_MAX_ENTRY_BYTES = 8 * 1024 * 1024


class CacheEntryTooLargeError(ValueError):
    """Raised when a cache entry exceeds the backend size contract."""

    def __init__(
        self,
        *,
        operation: str,
        actual_bytes: int,
        max_entry_bytes: int,
    ) -> None:
        self.operation = operation
        self.actual_bytes = actual_bytes
        self.max_entry_bytes = max_entry_bytes
        super().__init__(
            f"cache entry too large for {operation}: "
            f"{actual_bytes} bytes exceeds max_entry_bytes="
            f"{max_entry_bytes}",
        )


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

    def close(self) -> None: ...

    def __enter__(self) -> "CacheBackendProtocol": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
