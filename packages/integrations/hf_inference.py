from __future__ import annotations

import asyncio
import time

import httpx

from apps.web.config import settings
from packages.agent.providers.anthropic_provider import ANTHROPIC_OPUS_MODEL

_circuit_open_until: float = 0.0
_failure_count: int = 0


class HFInferenceError(Exception):
    pass


async def complete(*, model: str, prompt: str, node: str) -> str:
    global _circuit_open_until, _failure_count
    if time.time() < _circuit_open_until:
        return await _claude_fallback(prompt, node)

    if not settings.hf_token:
        return await _mock_response(prompt, node)

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {settings.hf_token}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 1024, "return_full_text": False}}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 429:
                await asyncio.sleep(2**attempt)
                continue
            if resp.status_code >= 500:
                raise HFInferenceError(f"HF {resp.status_code}")
            resp.raise_for_status()
            data = resp.json()
            _failure_count = 0
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return str(data[0]["generated_text"])
            if isinstance(data, dict) and "generated_text" in data:
                return str(data["generated_text"])
            return str(data)
        except (HFInferenceError, httpx.HTTPError):
            _failure_count += 1
            if _failure_count >= 5:
                _circuit_open_until = time.time() + 60
            if attempt == 2:
                return await _claude_fallback(prompt, node)
            await asyncio.sleep(2**attempt)
    return await _claude_fallback(prompt, node)


async def _claude_fallback(prompt: str, node: str) -> str:
    if not settings.anthropic_api_key:
        return await _mock_response(prompt, node)
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=ANTHROPIC_OPUS_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    block = msg.content[0]
    if hasattr(block, "text"):
        return block.text
    return str(block)


async def _mock_response(prompt: str, node: str) -> str:
    if node == "validate_output":
        return "no"
    if "JSON" in prompt:
        return (
            '{"summary": "Experienced professional.", "experience": "Led projects.",'
            ' "skills": "Python, SQL"}'
        )
    return "Experienced professional with relevant skills."
