from collections.abc import Callable
from typing import Any, TypeVar

from typing_extensions import Protocol

from cachepot.backend import CacheBackendProtocol
from cachepot.expire import ExpireSeconds
from cachepot.serializer import SerializerProtocol

T = TypeVar("T", contravariant=True)
S = TypeVar("S")


class CacheStoreProtocol(Protocol[T, S]):
    def get(self, key: T) -> S | None: ...

    def put(
        self,
        key: T,
        value: S,
        *,
        expire_seconds: ExpireSeconds | None = None,
    ) -> None: ...

    def proxy(
        self, original_function: Callable[..., S],
    ) -> Callable[..., S]: ...

    def remove(self, key: T) -> None: ...


class CacheStore(CacheStoreProtocol[T, S]):
    namespace: str
    key_serializer: SerializerProtocol[T]
    value_serializer: SerializerProtocol[S]
    backend: CacheBackendProtocol
    default_expire_seconds: ExpireSeconds

    def __init__(
        self,
        namespace: str,
        backend: CacheBackendProtocol,
        key_serializer: SerializerProtocol[T],
        value_serializer: SerializerProtocol[S],
        default_expire_seconds: ExpireSeconds,
    ) -> None:
        self.namespace = namespace
        self.key_serializer = key_serializer
        self.value_serializer = value_serializer
        self.backend = backend
        self.default_expire_seconds = default_expire_seconds

    def __get_real_key(self, key: T) -> bytes:
        serialized_key = self.key_serializer.serialize(key)
        return self.namespace.encode() + b":" + serialized_key

    def get(self, key: T) -> S | None:
        real_key = self.__get_real_key(key)
        loaded = self.backend.load(real_key)
        if loaded is None:
            return None
        return self.value_serializer.deserialize(loaded)

    def put(
        self,
        key: T,
        value: S,
        *,
        expire_seconds: ExpireSeconds | None = None,
    ) -> None:
        if expire_seconds is None:
            expire_seconds = self.default_expire_seconds
        real_key = self.__get_real_key(key)
        serialized_value = self.value_serializer.serialize(value)
        self.backend.save(
            real_key, serialized_value, expire_seconds=expire_seconds,
        )

    def proxy(self, original_function: Callable[..., S]) -> Callable[..., S]:
        def _proxy(
            *args: Any,
            cache_key: T,
            expire_seconds: ExpireSeconds | None = None,
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
        expire_seconds: ExpireSeconds | None,
        original_function: Callable[..., S],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> S:
        cached_result = self.get(cache_key)
        if cached_result is not None:
            return cached_result

        result = original_function(*args, **kwargs)
        self.put(cache_key, result, expire_seconds=expire_seconds)
        return result

    def remove(self, key: T) -> None:
        real_key = self.__get_real_key(key)
        self.backend.delete(real_key)
