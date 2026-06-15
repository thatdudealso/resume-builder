from __future__ import annotations

import pytest
import respx
import httpx

from packages.integrations.hf_inference import complete


@pytest.mark.asyncio
@respx.mock
async def test_hf_success(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.hf_token", "test-token")
    respx.post("https://api-inference.huggingface.co/models/test-model").mock(
        return_value=httpx.Response(200, json=[{"generated_text": "result text"}])
    )
    out = await complete(model="test-model", prompt="hi", node="rewrite_sections")
    assert out == "result text"


@pytest.mark.asyncio
@respx.mock
async def test_hf_fallback_on_500(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.hf_token", "test-token")
    monkeypatch.setattr("apps.web.config.settings.anthropic_api_key", "")
    respx.post("https://api-inference.huggingface.co/models/test-model").mock(
        return_value=httpx.Response(500, json={"error": "fail"})
    )
    out = await complete(model="test-model", prompt="hello", node="validate_output")
    assert out
