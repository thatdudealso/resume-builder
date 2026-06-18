from __future__ import annotations

from unittest.mock import MagicMock, patch

from packages.integrations.stripe_client import create_checkout_session


@patch("packages.integrations.stripe_client.stripe.checkout.Session.create")
def test_create_checkout_session(mock_create, monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_secret_key", "sk_test_real")
    monkeypatch.setattr("apps.web.config.settings.cors_origins", "http://localhost:8000")
    monkeypatch.setattr("apps.web.config.settings.run_unlock_price_usd", 3.99)
    mock_create.return_value = MagicMock(url="https://checkout.stripe.com/x")
    url = create_checkout_session(user_id="u1", run_id="r1", email="a@b.com")
    assert url.startswith("https://")
    line_items = mock_create.call_args.kwargs["line_items"]
    assert line_items[0]["price_data"]["unit_amount"] == 399
