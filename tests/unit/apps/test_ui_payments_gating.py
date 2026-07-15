from __future__ import annotations

from apps.web.ui.app import _billing_shows_payments, _should_show_support_link


def test_shows_payments_when_enabled_explicitly():
    assert _billing_shows_payments({"payments_enabled": True}) is True


def test_hides_payments_when_disabled_explicitly():
    assert _billing_shows_payments({"payments_enabled": False}) is False


def test_defaults_to_showing_payments_when_field_missing():
    # Backward-compatible default: an older/incomplete billing response should not
    # accidentally hide payment controls.
    assert _billing_shows_payments({}) is True


def test_support_link_hidden_when_payments_enabled():
    assert _should_show_support_link(payments_enabled=True, support_url="https://example.com") is False


def test_support_link_hidden_when_payments_disabled_but_no_url():
    assert _should_show_support_link(payments_enabled=False, support_url="") is False


def test_support_link_hidden_when_payments_disabled_but_whitespace_url():
    assert _should_show_support_link(payments_enabled=False, support_url="   ") is False


def test_support_link_shown_when_payments_disabled_and_url_provided():
    assert _should_show_support_link(payments_enabled=False, support_url="https://example.com") is True
