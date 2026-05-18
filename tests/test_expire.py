from datetime import timedelta

import pytest

from cachepot.expire import to_timedelta


def test_to_timedelta_float() -> None:
    assert to_timedelta(1.0) == timedelta(seconds=1.0)


def test_to_timedelta_int() -> None:
    assert to_timedelta(3) == timedelta(seconds=3)


def test_to_timedelta_timedelta() -> None:
    assert to_timedelta(timedelta(days=5)) == timedelta(days=5)


def test_to_timedelta_zero_is_valid() -> None:
    assert to_timedelta(0) == timedelta(0)


def test_to_timedelta_negative_int_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        to_timedelta(-1)


def test_to_timedelta_negative_float_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        to_timedelta(-0.5)


def test_to_timedelta_negative_timedelta_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        to_timedelta(timedelta(seconds=-60))
