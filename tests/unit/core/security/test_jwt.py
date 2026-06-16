from __future__ import annotations

import pytest

from packages.core.security.jwt import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from packages.core.security.sanitization import sanitize_text


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


@pytest.mark.asyncio
async def test_access_token_roundtrip():
    from uuid import uuid4

    uid = uuid4()
    token = create_access_token(uid)
    decoded = await decode_access_token(token)
    assert decoded == uid


def test_sanitize_strips_html():
    assert "<script>" not in sanitize_text("hello <script>alert(1)</script>")
