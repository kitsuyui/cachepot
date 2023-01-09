# cachepot

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cachepot.svg)](https://pypi.python.org/pypi/cachepot/)
[![PyPI](https://img.shields.io/pypi/v/cachepot.svg)](https://pypi.python.org/pypi/cachepot/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/cachepot.svg)](https://pypi.python.org/pypi/cachepot/)
[![Lint and Test Python](https://github.com/kitsuyui/cachepot/actions/workflows/python-test.yml/badge.svg)](https://github.com/kitsuyui/cachepot/actions/workflows/python-test.yml)
[![codecov](https://codecov.io/gh/kitsuyui/cachepot/branch/main/graph/badge.svg?token=mdzEJ8cwcB)](https://codecov.io/gh/kitsuyui/cachepot)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

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

### Proxy method

```python
result = store.proxy(some_func)(some_args)
```

is the equivalent of

```python
result = store.get(some_arg)
if result is None:
    result = some_func(some_args)
    store.set(result)
```

In short, this works as proxy. This helps to make codes straight forward.
proxy method can be passed two arguments `cache_key` and `expire_seconds`.

## Core idea

Serializers convert python objects into bytes.
Backends save/load bytes.
So serializers and backends are independent.
CacheStore is the facade of them.

- Python3 typing supports
- namespaces
- Proxy method

## Features

### Serializers

- str ... [cachepot.serializer.str.StringSerializer](https://github.com/kitsuyui/cachepot/blob/master/cachepot/serializer/str.py)
- [pickle](https://docs.python.org/3/library/pickle.html) ... [cachepot.serializer.pickle.PickleSerializer](https://github.com/kitsuyui/cachepot/blob/master/cachepot/serializer/pickle.py)
- [JSON](https://tools.ietf.org/html/rfc8259) ... [cachepot.serializer.json.JSONSerializer](https://github.com/kitsuyui/cachepot/blob/master/cachepot/serializer/json.py)

And more serializers you can define.

### Backends

- Save to files ... [cachepot.backend.filesystem.FileSystemCacheBackend](https://github.com/kitsuyui/cachepot/blob/master/cachepot/backend/filesystem.py)
- Save to SQLite3 DB records ... [cachepot.backend.sqlite.SQLiteCacheBackend](https://github.com/kitsuyui/cachepot/blob/master/cachepot/backend/sqlite.py)
- Save to Redis DB ... [cachepot.backend.redis.RedisCacheBackend](https://github.com/kitsuyui/cachepot/blob/master/cachepot/backend/redis.py)

Of course you can define own backend.

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
