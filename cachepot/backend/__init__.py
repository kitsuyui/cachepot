from types import TracebackType
from typing import Protocol

from cachepot.expire import Expiry


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

    def delete_expired(self) -> int: ...

    def close(self) -> None: ...

    def __enter__(self) -> "CacheBackendProtocol": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
