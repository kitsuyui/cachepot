from datetime import timedelta
from typing import Union

ExpireSeconds = Union[int, float, timedelta]


def to_timedelta(expire_seconds: ExpireSeconds) -> timedelta:
    if isinstance(expire_seconds, (int, float)):
        return timedelta(seconds=expire_seconds)
    return expire_seconds
