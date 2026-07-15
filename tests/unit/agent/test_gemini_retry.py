import pytest
import httpx
from packages.agent.providers.gemini_provider import GeminiProvider


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
    def json(self): return self._payload
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("e", request=None, response=self)


@pytest.mark.asyncio
async def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("packages.agent.providers.gemini_provider.settings.gemini_api_key", "k")
    calls = {"n": 0}
    good = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k):
            calls["n"] += 1
            return _Resp(429) if calls["n"] == 1 else _Resp(200, good)

    monkeypatch.setattr("packages.agent.providers.gemini_provider.httpx.AsyncClient",
                        lambda *a, **k: Client())
    async def _no_sleep(*_a, **_k):
        return None

    monkeypatch.setattr("packages.agent.providers.gemini_provider.asyncio.sleep", _no_sleep)
    from packages.agent.providers.base import AgentTask
    out = await GeminiProvider().complete(AgentTask.JD_ANALYSIS, "p")
    assert out == "ok"
    assert calls["n"] == 2
