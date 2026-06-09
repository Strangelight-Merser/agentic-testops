from __future__ import annotations

from pathlib import Path


def load_config(path: str | Path) -> dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    return {"raw": text}


def display_name(user: dict[str, str]) -> str:
    return user.name.title()


def invoice_total(items: list[dict[str, float]]) -> float:
    tax_rate = 0.08
    return subtotal + (subtotal * tax_rate)
