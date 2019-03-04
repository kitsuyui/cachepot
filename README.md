# cachepot

[![image](https://img.shields.io/pypi/v/cachepot.svg)](https://pypi.org/project/cachepot/)
[![image](https://img.shields.io/pypi/l/cachepot.svg)](https://pypi.org/project/cachepot/)

Yet another Python cache library. This has Python 3 typing hints.

## Installation

```
$ pip install cachepot
```

## Usage

```python
>>> from cachepot.store import CacheStore
>>> from cachepot.backend.filesystem import FileSystemCacheBackend
>>> from cachepot.serializer.pickle import PickleSerializer
>>> store = CacheStore(
...     namespace='testing',
...     key_serializer=PickleSerializer(),
...     value_serializer=PickleSerializer(),
...     backend=FileSystemCacheBackend('/tmp'),
...     default_expire_seconds=3600,
... )
>>> store.put({'some': 'key'}, {'some': 'value'})
>>> store.get({'some': 'key'})
{'some': 'value'}
>>> store.put({'some': 'short expiring key'}, {'some': 'value'}, expire_seconds=10)
```

### Proxy interface

```python
result = store.proxy(some_func)(some_args)
```

is same as

```python
result = store.get(some_arg)
if result is None:
    result = some_func(some_args)
    store.set(result)
```

In short, this works as proxy. This helps to make codes straight forward.
proxy method can be passed two arguments `cache_key` and `expire_seconds`.

## Core Idea

- Typing supports
- Generic serializers ... [pickle](https://docs.python.org/3/library/pickle.html), [JSON](https://tools.ietf.org/html/rfc8259), and more serializers you can define.
- Generic backends ... Currently supports only filesystem backend and sqlite3 backend. But it is not so difficult to add Redis or the other KVS backends. And of course you can define own backend.
- Proxy interface

## Development

You can install requirements with pipenv

```shell
$ pipenv install --dev
```

### Test

```shell
$ flake8
$ mypy .
$ python3 -m unittest discover
```

# LICENSE

The 3-Clause BSD License. See also LICENSE file.
