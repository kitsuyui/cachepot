from datetime import timedelta

from cachepot.expire import to_timedelta


def test_to_timedelta_float() -> None:
    assert to_timedelta(1.0) == timedelta(seconds=1.0)


def test_to_timedelta_int() -> None:
    assert to_timedelta(3) == timedelta(seconds=3)


def test_to_timedelta_timedelta() -> None:
    assert to_timedelta(timedelta(days=5)) == timedelta(days=5)
