from datetime import timedelta

Expiry = int | float | timedelta

# Backward-compatible alias
ExpireSeconds = Expiry


def _assert_non_negative(value: timedelta, original: Expiry) -> None:
    if value.total_seconds() < 0:
        raise ValueError(
            f"expire_seconds must be non-negative, got {original!r}",
        )


def to_timedelta(expire_seconds: Expiry) -> timedelta:
    if isinstance(expire_seconds, (int, float)):
        result = timedelta(seconds=expire_seconds)
    else:
        result = expire_seconds
    _assert_non_negative(result, expire_seconds)
    return result
