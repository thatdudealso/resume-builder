from __future__ import annotations

from apps.web.ui.app import _billing_shows_payments


def test_shows_payments_when_enabled_explicitly():
    assert _billing_shows_payments({"payments_enabled": True}) is True


def test_hides_payments_when_disabled_explicitly():
    assert _billing_shows_payments({"payments_enabled": False}) is False


def test_defaults_to_showing_payments_when_field_missing():
    # Backward-compatible default: an older/incomplete billing response should not
    # accidentally hide payment controls.
    assert _billing_shows_payments({}) is True
