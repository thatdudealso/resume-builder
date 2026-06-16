from __future__ import annotations

import httpx
import pytest
import respx

from packages.integrations.hf_inference import complete


@pytest.mark.asyncio
@respx.mock
async def test_hf_429_then_mock_fallback(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.hf_token", "tok")
    monkeypatch.setattr("apps.web.config.settings.anthropic_api_key", "")
    route = respx.post("https://api-inference.huggingface.co/models/m").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(429, json={"error": "rate limit"}),
        ]
    )
    out = await complete(model="m", prompt="x", node="rewrite_sections")
    assert out
    assert route.call_count == 3
