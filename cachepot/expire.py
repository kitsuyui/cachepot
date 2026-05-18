from datetime import timedelta

ExpireSeconds = int | float | timedelta


def _assert_non_negative(value: timedelta, original: ExpireSeconds) -> None:
    if value.total_seconds() < 0:
        raise ValueError(
            f"expire_seconds must be non-negative, got {original!r}",
        )


def to_timedelta(expire_seconds: ExpireSeconds) -> timedelta:
    if isinstance(expire_seconds, (int, float)):
        result = timedelta(seconds=expire_seconds)
    else:
        result = expire_seconds
    _assert_non_negative(result, expire_seconds)
    return result
