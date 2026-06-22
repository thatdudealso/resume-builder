from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from packages.integrations.stripe_client import create_checkout_session


@patch("packages.integrations.stripe_client.stripe.checkout.Session.create")
def test_create_checkout_session(mock_create, monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_secret_key", "sk_test_real")
    monkeypatch.setattr("apps.web.config.settings.cors_origins", "http://localhost:8000")
    monkeypatch.setattr("apps.web.config.settings.run_unlock_price_usd", 3.99)
    mock_create.return_value = MagicMock(url="https://checkout.stripe.com/x", id="cs_test_123")
    result = create_checkout_session(
        user_id="u1", run_id="r1", email="a@b.com", resume_id="res1"
    )
    assert result.url.startswith("https://")
    assert result.session_id == "cs_test_123"
    line_items = mock_create.call_args.kwargs["line_items"]
    assert line_items[0]["price_data"]["unit_amount"] == 399


@patch("packages.integrations.stripe_client.stripe.checkout.Session.create")
def test_create_checkout_session_requires_url(mock_create, monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_secret_key", "sk_test_real")
    monkeypatch.setattr("apps.web.config.settings.cors_origins", "http://localhost:8000")
    mock_create.return_value = MagicMock(url=None, id="cs_test_123")
    with pytest.raises(RuntimeError, match="did not return a URL"):
        create_checkout_session(
            user_id="u1", run_id="r1", email="a@b.com", resume_id="res1"
        )
