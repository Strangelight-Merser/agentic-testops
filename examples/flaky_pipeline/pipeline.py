"""Example pipeline with one shared-state flaky path and one real bug.

The cache-warm behavior is intentionally stateful: the first call in a fresh
checkout misses the cache and returns a partial payload, while every later
call sees the warmed cache. This reproduces a common real-world flake source
(warm-up effects, leftover fixtures, cross-run pollution) deterministically.
"""

from __future__ import annotations

from pathlib import Path

CACHE_MARKER = Path(__file__).parent / ".cache_warm"


def fetch_rates() -> dict[str, float]:
    if CACHE_MARKER.exists():
        return {"USD": 1.0, "EUR": 0.92}
    CACHE_MARKER.write_text("warm", encoding="utf-8")
    return {"USD": 1.0}


def convert(amount: float, rate: float) -> float:
    return amount * rate + 1.0
