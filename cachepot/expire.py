from datetime import timedelta

ExpireSeconds = int | float | timedelta


def to_timedelta(expire_seconds: ExpireSeconds) -> timedelta:
    if isinstance(expire_seconds, (int, float)):
        return timedelta(seconds=expire_seconds)
    return expire_seconds
