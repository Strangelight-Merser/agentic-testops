import pytest

from calculator import average, divide


def test_divide_rejects_zero() -> None:
    with pytest.raises(ValueError):
        divide(10, 0)


def test_average_empty_list_returns_zero() -> None:
    assert average([]) == 0
