from __future__ import annotations

import httpx


async def openai_compatible_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    json_mode: bool = False,
    timeout: float = 90.0,
) -> str:
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Empty LLM response")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise ValueError("Empty LLM message content")
    return str(content)
