# Examples

This directory contains small, importable usage examples for building concrete
`CacheStore` classes from cachepot's serializers and backends.

The examples are intentionally kept outside the `cachepot` package so they do
not become part of the public library API. Tests import them as smoke coverage
to keep the snippets working as the library evolves.
