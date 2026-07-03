import inspect
import threading
import warnings
import weakref
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from cachepot.backend import CacheBackendProtocol, DeletedExpiredCount
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

    def delete_expired(self) -> DeletedExpiredCount:
        """Delete expired entries and return the removed count when known.

        Implementations backed by a TTL-aware store (e.g. Redis) may expire
        entries autonomously.  Such backends return ``None`` when the deleted
        count is not observable.  Do not use this return value as a health or
        activity metric unless the selected backend documents a count.
        """
        ...


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
        self._key_locks: weakref.WeakValueDictionary[bytes, Any] = (
            weakref.WeakValueDictionary()
        )

    def __get_real_key(self, key: T) -> bytes:
        serialized_key = self.key_serializer.serialize(key)
        ns_bytes = self.namespace.encode()
        return len(ns_bytes).to_bytes(4, "big") + ns_bytes + serialized_key

    def _get_or_create_key_lock(self, real_key: bytes) -> Any:
        lock = self._key_locks.get(real_key)
        if lock is None:
            lock = threading.RLock()
            self._key_locks[real_key] = lock
        return lock

    def _real_key_and_lock(self, key: T) -> tuple[bytes, Any]:
        with self._lock:
            real_key = self.__get_real_key(key)
            return real_key, self._get_or_create_key_lock(real_key)

    def _deserialize(self, loaded: bytes, key: T) -> S:
        try:
            return self.value_serializer.deserialize(loaded)
        except Exception as exc:
            raise RuntimeError(
                f"Cache deserialization failed: "
                f"namespace={self.namespace!r}, key={key!r}",
            ) from exc

    def get(self, key: T) -> S | None:
        real_key, key_lock = self._real_key_and_lock(key)
        with key_lock, self._lock:
            loaded = self.backend.load(real_key)
            if loaded is None:
                return None
            return self._deserialize(loaded, key)

    def has(self, key: T) -> bool:
        real_key, key_lock = self._real_key_and_lock(key)
        with key_lock, self._lock:
            return self.backend.exists(real_key)

    def put(
        self,
        key: T,
        value: S,
        *,
        expire_seconds: Expiry | None = None,
    ) -> None:
        real_key, key_lock = self._real_key_and_lock(key)
        with key_lock, self._lock:
            if expire_seconds is None:
                expire_seconds = self.default_expire_seconds
            serialized_value = self.value_serializer.serialize(value)
            self.backend.save(
                real_key,
                serialized_value,
                expire_seconds=expire_seconds,
            )

    _RESERVED_PROXY_PARAMS: frozenset[str] = frozenset(
        {"cache_key", "expire_seconds"},
    )

    @staticmethod
    def _proxy_conflicts(fn: Callable[..., Any]) -> frozenset[str]:
        try:
            params = inspect.signature(fn).parameters.keys()
            return CacheStore._RESERVED_PROXY_PARAMS & params
        except (TypeError, ValueError):
            return frozenset()

    def _make_proxy(
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

    def proxy(
        self,
        original_function: Callable[..., S],
    ) -> CacheProxyProtocol[T, S]:
        """Return a caching proxy for *original_function*.

        The proxy injects ``cache_key`` and ``expire_seconds`` as its own
        keyword-only arguments before forwarding the remaining ``**kwargs``
        to *original_function*.  Therefore *original_function* must **not**
        declare parameters named ``cache_key`` or ``expire_seconds``; if it
        does, those arguments are silently captured by the proxy and never
        reach the wrapped function, causing a ``TypeError`` at call time.

        A ``TypeError`` is raised at proxy creation time when such a conflict
        is detected, before any calls are made.
        """
        conflicts = self._proxy_conflicts(original_function)
        if conflicts:
            names = ", ".join(f"'{n}'" for n in sorted(conflicts))
            raise TypeError(
                f"proxy() cannot wrap a function whose parameter(s) "
                f"({names}) share a name with proxy's reserved keyword "
                f"arguments 'cache_key' and 'expire_seconds'.",
            )
        return self._make_proxy(original_function)

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
        real_key, key_lock = self._real_key_and_lock(cache_key)
        with key_lock:
            with self._lock:
                loaded = self.backend.load(real_key)
                if loaded is not None:
                    return self._deserialize(loaded, cache_key)

            result = original_function(*args, **kwargs)
            self._put_or_warn(cache_key, result, expire_seconds)
            return result

    def _put_or_warn(
        self,
        cache_key: T,
        result: S,
        expire_seconds: Expiry | None,
    ) -> None:
        try:
            self.put(cache_key, result, expire_seconds=expire_seconds)
        except Exception as exc:
            warnings.warn(
                f"Cache write failed: "
                f"namespace={self.namespace!r}, "
                f"key={cache_key!r}: {exc}",
                stacklevel=4,
            )

    def delete(self, key: T) -> None:
        real_key, key_lock = self._real_key_and_lock(key)
        with key_lock, self._lock:
            self.backend.delete(real_key)

    def delete_expired(self) -> DeletedExpiredCount:
        return self.backend.delete_expired()
