from __future__ import annotations

from pipeline import convert, fetch_rates


def test_fetch_rates_includes_eur():
    rates = fetch_rates()
    assert "EUR" in rates


def test_convert_applies_rate_exactly():
    assert convert(10.0, 2.0) == 20.0
