from __future__ import annotations

import httpx
import pytest
import respx

from packages.integrations.hf_inference import HFInferenceError, complete


@pytest.mark.asyncio
@respx.mock
async def test_hf_429_then_raises(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.hf_token", "tok")
    monkeypatch.setattr("packages.integrations.hf_inference._circuit_open_until", 0.0)
    monkeypatch.setattr("packages.integrations.hf_inference._failure_count", 0)
    route = respx.post("https://api-inference.huggingface.co/models/m").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(429, json={"error": "rate limit"}),
        ]
    )
    with pytest.raises(HFInferenceError):
        await complete(model="m", prompt="x", node="rewrite_sections")
    assert route.call_count == 3
