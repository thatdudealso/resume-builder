from __future__ import annotations

import pytest

from packages.integrations.crypto.nowpayments import create_invoice, verify_ipn_signature


@pytest.mark.asyncio
async def test_create_invoice_test_mode():
    result = await create_invoice(user_id="u1", run_id="r1", pay_currency="eth")
    assert "pay_address" in result


def test_verify_ipn_fails_without_secret(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.nowpayments_ipn_secret", "secret")
    monkeypatch.setattr("apps.web.config.settings.env", "prod")
    assert verify_ipn_signature(b"{}", "bad") is False
