# cachepot

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cachepot.svg)](https://pypi.python.org/pypi/cachepot/)
[![PyPI](https://img.shields.io/pypi/v/cachepot.svg)](https://pypi.python.org/pypi/cachepot/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/cachepot.svg)](https://pypi.python.org/pypi/cachepot/)
[![Lint and Test Python](https://github.com/kitsuyui/cachepot/actions/workflows/python-test.yml/badge.svg)](https://github.com/kitsuyui/cachepot/actions/workflows/python-test.yml)
![Coverage](https://raw.githubusercontent.com/kitsuyui/octocov-central/main/badges/kitsuyui/cachepot/coverage.svg)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

Yet another Python cache library. This has Python 3 typing hints.

## Installation

```
$ pip install cachepot
```

## Usage

```python
>>> from cachepot import CacheStore, FileSystemCacheBackend
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
>>> store.delete_expired()
0
```

`delete_expired()` returns the number of entries removed when the backend can
observe that count.  Redis handles TTL expiry server-side, so its backend
returns `None` when the deleted-entry count is unknown.

> **Security note**: `PickleSerializer` uses Python's `pickle` module, which can
> execute arbitrary code during deserialization. The serializer is intentionally
> not exported from `cachepot`'s top-level namespace. Import it explicitly from
> `cachepot.serializer.pickle` only when the cache backend storage is fully
> under your control and trusted. For untrusted environments, prefer
> `JsonSerializer` or `MsgpackSerializer` instead.

### Proxy method

```python
result = store.proxy(some_func)(some_args, cache_key=some_arg)
```

is the equivalent of

```python
result = store.get(some_arg)
if result is None:
    result = some_func(some_args)
    store.put(some_arg, result)
```

In short, this works as proxy. This helps to make codes straight forward.
The proxied function requires the keyword-only argument `cache_key` and
can also accept `expire_seconds`.

When a proxied cache write fails, `cachepot` keeps returning the computed
result, emits a `CachepotWarning`, logs the failure on the `cachepot.store`
logger, and increments `store.cache_write_failures`. This lets applications
forward failures to their existing logging or metrics pipeline without giving
up graceful degradation.

## Core idea

Serializers convert python objects into bytes.
Backends save/load bytes.
So serializers and backends are independent.
CacheStore is the facade of them.

- Python3 typing supports
- namespaces
- Proxy method
- Expired entry cleanup

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

This repository uses [lefthook](https://lefthook.dev/) to run the same checks as CI
locally, so problems surface before they reach CI.

```sh
# Install dependencies
uv sync

# Install the Git hooks (once; requires lefthook on your PATH)
lefthook install
```

Once installed, the hooks run automatically:

- **pre-commit**: `uv run poe check`
- **pre-push**: `uv run poe check` and `uv run poe test`

You can also run the checks manually:

```sh
uv run poe check
uv run poe test
```

CI still runs the full matrix (see `.github/workflows/`); the hooks only bring that
feedback earlier on your machine.

# LICENSE

The 3-Clause BSD License. See also LICENSE file.
