from __future__ import annotations

import inspect

import pytest

import packages.integrations.hf_inference as hf


def test_no_anthropic_reference_in_source():
    src = inspect.getsource(hf)
    assert "anthropic" not in src.lower()


@pytest.mark.asyncio
async def test_raises_on_exhausted_retries(monkeypatch):
    monkeypatch.setattr(hf.settings, "hf_token", "x")

    class Boom:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise hf.httpx.HTTPError("down")

    monkeypatch.setattr(hf.httpx, "AsyncClient", lambda *a, **k: Boom())
    with pytest.raises(hf.HFInferenceError):
        await hf.complete(model="m", prompt="p", node="analyze_inputs")
