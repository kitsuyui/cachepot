import threading
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import Expiry
from cachepot.serializer import SerializerProtocol

T = TypeVar("T", contravariant=True)
S = TypeVar("S")
S_co = TypeVar("S_co", covariant=True)


class CacheProxyProtocol(Protocol[T, S_co]):
    def __call__(
        self,
        *args: Any,
        cache_key: T,
        expire_seconds: Expiry | None = None,
        **kwargs: Any,
    ) -> S_co: ...


class CacheStoreProtocol(Protocol[T, S]):
    def get(self, key: T) -> S | None: ...

    def has(self, key: T) -> bool: ...

    def put(
        self,
        key: T,
        value: S,
        *,
        expire_seconds: Expiry | None = None,
    ) -> None: ...

    def proxy(
        self,
        original_function: Callable[..., S],
    ) -> CacheProxyProtocol[T, S]: ...

    def delete(self, key: T) -> None: ...

    def delete_expired(self) -> int: ...


class CacheStore(CacheStoreProtocol[T, S]):
    namespace: str
    key_serializer: SerializerProtocol[T]
    value_serializer: SerializerProtocol[S]
    backend: CacheBackendProtocol
    default_expire_seconds: Expiry

    def __init__(
        self,
        namespace: str,
        backend: CacheBackendProtocol,
        key_serializer: SerializerProtocol[T],
        value_serializer: SerializerProtocol[S],
        default_expire_seconds: Expiry,
    ) -> None:
        self.namespace = namespace
        self.key_serializer = key_serializer
        self.value_serializer = value_serializer
        self.backend = backend
        self.default_expire_seconds = default_expire_seconds
        self._lock = threading.RLock()

    def __get_real_key(self, key: T) -> bytes:
        serialized_key = self.key_serializer.serialize(key)
        ns_bytes = self.namespace.encode()
        return len(ns_bytes).to_bytes(4, "big") + ns_bytes + serialized_key

    def get(self, key: T) -> S | None:
        real_key = self.__get_real_key(key)
        loaded = self.backend.load(real_key)
        if loaded is None:
            return None
        return self.value_serializer.deserialize(loaded)

    def has(self, key: T) -> bool:
        real_key = self.__get_real_key(key)
        return self.backend.exists(real_key)

    def put(
        self,
        key: T,
        value: S,
        *,
        expire_seconds: Expiry | None = None,
    ) -> None:
        if expire_seconds is None:
            expire_seconds = self.default_expire_seconds
        real_key = self.__get_real_key(key)
        serialized_value = self.value_serializer.serialize(value)
        self.backend.save(
            real_key,
            serialized_value,
            expire_seconds=expire_seconds,
        )

    def proxy(
        self,
        original_function: Callable[..., S],
    ) -> CacheProxyProtocol[T, S]:
        def _proxy(
            *args: Any,
            cache_key: T,
            expire_seconds: Expiry | None = None,
            **kwargs: Any,
        ) -> S:
            return self.__load_or_compute(
                cache_key=cache_key,
                expire_seconds=expire_seconds,
                original_function=original_function,
                args=args,
                kwargs=kwargs,
            )

        return _proxy

    def __load_or_compute(
        self,
        *,
        cache_key: T,
        expire_seconds: Expiry | None,
        original_function: Callable[..., S],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> S:
        # Inspect the backend directly so a stored ``None`` value is
        # distinguishable from a cache miss (the backend returns ``None``
        # only when the key is absent; a stored value is always bytes).
        real_key = self.__get_real_key(cache_key)
        with self._lock:
            loaded = self.backend.load(real_key)
            if loaded is not None:
                return self.value_serializer.deserialize(loaded)

            result = original_function(*args, **kwargs)
            self.put(cache_key, result, expire_seconds=expire_seconds)
            return result

    def delete(self, key: T) -> None:
        real_key = self.__get_real_key(key)
        self.backend.delete(real_key)

    def delete_expired(self) -> int:
        return self.backend.delete_expired()
