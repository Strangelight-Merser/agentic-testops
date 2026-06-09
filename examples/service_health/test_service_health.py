from __future__ import annotations

from service_health import display_name, invoice_total, load_config


def test_load_config_handles_missing_file():
    assert load_config("missing.env") == {"raw": ""}


def test_display_name_accepts_dict_user():
    assert display_name({"name": "ada lovelace"}) == "Ada Lovelace"


def test_invoice_total_sums_items_with_tax():
    assert invoice_total([{"amount": 10.0}, {"amount": 5.0}]) == 16.2
