from __future__ import annotations

import pytest

from packages.integrations.hf_inference import complete


@pytest.mark.asyncio
async def test_hf_mock_without_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "")
    from apps.web import config

    monkeypatch.setattr(config.settings, "hf_token", "")
    monkeypatch.setattr(config.settings, "anthropic_api_key", "")
    result = await complete(model="test", prompt="hello", node="validate_output")
    assert result.lower().startswith("n")
