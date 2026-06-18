from example import (
    FileSystemJSONCacheStore,
    SimpleFileSystemCacheStore,
    example_usage,
)


def test_simple_filesystem_cache_store(tmp_path) -> None:
    store = SimpleFileSystemCacheStore("testing", directory=str(tmp_path))

    store.put("key", 1)

    assert store.get("key") == 1


def test_filesystem_json_cache_store(tmp_path) -> None:
    store = FileSystemJSONCacheStore("testing", directory=str(tmp_path))

    store.put("key", {"value": [1, 2, 3]})

    assert store.get("key") == {"value": [1, 2, 3]}


def test_example_usage_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    example_usage()
