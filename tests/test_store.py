import concurrent.futures
import functools
import tempfile
import time
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from typing_extensions import assert_type

import cachepot
from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.serializer.pickle import PickleSerializer
from cachepot.serializer.str import StringSerializer
from cachepot.store import CacheProxyProtocol, CacheStore

if TYPE_CHECKING:
    typed_proxy = cast(CacheProxyProtocol[str, int], None)
    assert_type(typed_proxy(1, cache_key="key"), int)

    typed_store = cast(CacheStore[str, int], None)
    proxied_increment = typed_store.proxy(lambda value: value + 1)
    assert_type(proxied_increment(1, cache_key="key"), int)
    assert_type(typed_store.delete_expired(), int)


def test_basis() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=1,
        )
        cachestore.put("x", 1)
        assert cachestore.get("x") == 1
        cachestore.delete("x")
        assert cachestore.get("x") is None
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3
        assert cachestore.get("y") == 3

        # expire
        time.sleep(2)
        assert cachestore.get("y") is None
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3


def test_has_distinguishes_miss_from_stored_none() -> None:
    """has() returns False on miss and True on hit, even when the stored value
    is None — a distinction that get() cannot express."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store: CacheStore[str, None] = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )
        assert not store.has("k")
        store.put("k", None)
        assert store.has("k")
        assert store.get("k") is None
        store.delete("k")
        assert not store.has("k")


def test_delete_expired() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=1,
        )
        store.put("expired", 1)
        store.put("live", 2, expire_seconds=60)

        time.sleep(2)

        assert store.delete_expired() == 1
        assert store.get("expired") is None
        assert store.get("live") == 2
        assert store.delete_expired() == 0


def test_proxy_caches_none_return_value() -> None:
    """A function whose result is ``None`` must only be executed once
    per cached call, even though ``None`` is also the sentinel the
    serializer is allowed to round-trip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )

        call_count = 0

        def returns_none() -> None:
            nonlocal call_count
            call_count += 1

        proxied = cachestore.proxy(returns_none)
        assert proxied(cache_key="none-key") is None
        assert proxied(cache_key="none-key") is None
        assert call_count == 1


class _CountingFunction:
    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self) -> int:
        self.call_count += 1
        time.sleep(0.05)
        return 42


def _invoke(fn: Callable[[], int]) -> int:
    return fn()


def _run_concurrent(fn: Callable[[], int], n: int) -> list[int]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(_invoke, [fn] * n))


def test_proxy_no_double_execution_under_concurrency() -> None:
    """Concurrent cache misses on the same key must not execute the
    original function more than once.

    All workers start simultaneously; the first acquires the store lock,
    computes the result (with a brief sleep so others block on the lock),
    stores it, then releases.  The remaining workers find a cache hit and
    return without re-executing the function.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )
        fn = _CountingFunction()
        proxied = functools.partial(
            store.proxy(fn),
            cache_key="concurrent-key",
        )
        results = _run_concurrent(proxied, 8)
        assert fn.call_count == 1
        assert results == [42] * 8


def _returns_seven() -> int:
    return 7


def test_proxy_nested_same_store_does_not_deadlock() -> None:
    """A proxy whose original function calls another proxy on the same store
    must not deadlock.  Previously this failed because the store used a
    non-reentrant Lock and the inner proxy tried to re-acquire it from the
    same thread while the outer one held it.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )
        inner_proxied = store.proxy(_returns_seven)

        def outer() -> int:
            return inner_proxied(cache_key="inner-key") + 1

        outer_proxied = store.proxy(outer)
        assert outer_proxied(cache_key="outer-key") == 8
        assert outer_proxied(cache_key="outer-key") == 8


def test_namespace_key_no_collision() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store_a = CacheStore(
            namespace="a",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )
        store_ab = CacheStore(
            namespace="a:b",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )
        store_a.put("b:c", 1)
        store_ab.put("c", 2)
        assert store_a.get("b:c") == 1
        assert store_ab.get("c") == 2


def test_proxy_requires_cache_key_at_runtime() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cachestore = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )

        proxied = cachestore.proxy(lambda: 3)
        with pytest.raises(TypeError, match="cache_key"):
            proxied()  # type: ignore[call-arg]


def test_proxy_returns_result_when_backend_write_fails() -> None:
    """proxy() must return the computed result even when write fails.

    A disk-full or DB error must not discard an already-executed result.
    A warning is issued so callers can observe the failure.
    """
    backend = MagicMock()
    backend.load.return_value = None
    backend.save.side_effect = OSError("No space left on device")

    store: CacheStore[str, int] = CacheStore(
        namespace="testing",
        key_serializer=StringSerializer(),
        value_serializer=PickleSerializer(),
        backend=backend,
        default_expire_seconds=60,
    )

    call_count = 0

    def expensive() -> int:
        nonlocal call_count
        call_count += 1
        return 99

    proxied = store.proxy(expensive)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = proxied(cache_key="k")

    assert result == 99
    assert call_count == 1
    cache_write_warnings = [
        warning
        for warning in caught
        if "Cache write failed" in str(warning.message)
    ]
    assert len(cache_write_warnings) == 1
    assert "testing" in str(cache_write_warnings[0].message)
    assert issubclass(
        cache_write_warnings[0].category, cachepot.CachepotWarning,
    )


def _make_store(tmpdir: str) -> CacheStore[str, str]:
    return CacheStore(
        namespace="testing",
        key_serializer=StringSerializer(),
        value_serializer=PickleSerializer(),
        backend=FileSystemCacheBackend(tmpdir),
        default_expire_seconds=60,
    )


def test_proxy_rejects_function_with_cache_key_param() -> None:
    """proxy() raises TypeError at creation time when the wrapped function
    has a parameter named 'cache_key', because the proxy captures it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)

        def fn(*, cache_key: str) -> str:
            return cache_key

        with pytest.raises(TypeError, match="cache_key"):
            store.proxy(fn)


def test_proxy_rejects_function_with_expire_seconds_param() -> None:
    """proxy() raises TypeError at creation time when the wrapped function
    has a parameter named 'expire_seconds', because the proxy captures it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)

        def fn(*, expire_seconds: int) -> str:
            return str(expire_seconds)

        with pytest.raises(TypeError, match="expire_seconds"):
            store.proxy(fn)


def test_direct_put_get_is_thread_safe() -> None:
    """Concurrent direct put()/get() calls must not corrupt the cache.

    Multiple threads writing different integer values to the same key must
    each receive a valid integer back from get(), never None or an exception,
    proving that get() and put() are protected by the same store lock as
    proxy() / __load_or_compute().
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store: CacheStore[str, int] = CacheStore(
            namespace="testing",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )

        def put_then_get(i: int) -> int | None:
            store.put("shared", i)
            return store.get("shared")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(put_then_get, range(8)))

        assert all(isinstance(r, int) for r in results)


def test_get_raises_with_key_context_on_deserialize_failure() -> None:
    """get() must include namespace/key in the error on corrupt data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CacheStore(
            namespace="my-ns",
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(tmpdir),
            default_expire_seconds=60,
        )
        # Write corrupted bytes directly via the backend
        real_key = store._CacheStore__get_real_key("bad-key")  # type: ignore[attr-defined]
        store.backend.save(real_key, b"\xff\xfe corrupted", expire_seconds=60)

        with pytest.raises(RuntimeError, match="my-ns") as exc_info:
            store.get("bad-key")
        assert "bad-key" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None
