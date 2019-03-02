from typing import Any

from cachepot.backend.filesystem import FileSystemCacheBackend
from cachepot.serializer.json import JSONSerializer, JSONType
from cachepot.serializer.pickle import PickleSerializer
from cachepot.serializer.str import StringSerializer
from cachepot.store import CacheStore


class SimpleFileSystemCacheStore(CacheStore[str, Any]):
    namespace: str

    def __init__(
        self,
        namespace: str,
        *,
        directory: str = 'tmp',
    ):
        super().__init__(
            namespace=namespace,
            key_serializer=StringSerializer(),
            value_serializer=PickleSerializer(),
            backend=FileSystemCacheBackend(directory),
            default_expire_seconds=3600,
        )


class FileSystemJSONCacheStore(CacheStore[str, JSONType]):
    namespace: str

    def __init__(
        self,
        namespace: str,
        *,
        directory: str = 'tmp',
    ):
        super().__init__(
            namespace=namespace,
            key_serializer=StringSerializer(),
            value_serializer=JSONSerializer(),
            backend=FileSystemCacheBackend(directory),
            default_expire_seconds=3600,
        )


def example_usage() -> None:
    cachestore = SimpleFileSystemCacheStore('example', directory='./tmp')
    cachestore.put('x', 1)
    assert cachestore.get('x') == 1
    cachestore.remove('x')
    assert cachestore.get('x') is None
    assert cachestore.proxy(lambda: 3)(cache_key='y') == 3
    assert cachestore.proxy(lambda: 3)(cache_key='y') == 3
