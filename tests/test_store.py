import concurrent.futures
import functools
import tempfile
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import pytest
from typing_extensions import assert_type

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
        cachestore.remove("x")
        assert cachestore.get("x") is None
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3
        assert cachestore.get("y") == 3

        # expire
        time.sleep(2)
        assert cachestore.get("y") is None
        assert cachestore.proxy(lambda: 3)(cache_key="y") == 3


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
