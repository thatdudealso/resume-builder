from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import (
    _get_or_create_device_user_id,
    _request_fingerprint,
    get_current_user,
    get_current_user_id,
)
from packages.core.security.jwt import create_access_token, register_user
from packages.db.models.user import User


def _mock_request(
    *,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> MagicMock:
    request = MagicMock()
    request.headers = headers or {}
    request.cookies = cookies or {}
    client = MagicMock()
    client.host = client_host
    request.client = client
    return request


# ---------------------------------------------------------------------------
# _request_fingerprint
# ---------------------------------------------------------------------------


def test_request_fingerprint_from_header():
    req = _mock_request(headers={"X-Device-Fingerprint": "abc123"})
    assert _request_fingerprint(req) == "abc123"


def test_request_fingerprint_from_cookie():
    req = _mock_request(cookies={"rb_device_fingerprint": "cookiefp"})
    assert _request_fingerprint(req) == "cookiefp"


def test_request_fingerprint_whitespace_only_returns_none():
    req = _mock_request(headers={"X-Device-Fingerprint": "   "})
    assert _request_fingerprint(req) is None


def test_request_fingerprint_missing_returns_none():
    req = _mock_request()  # empty headers and cookies dicts
    assert _request_fingerprint(req) is None


def test_request_fingerprint_long_value_is_hashed():
    long_fp = "x" * 65
    req = _mock_request(headers={"X-Device-Fingerprint": long_fp})
    result = _request_fingerprint(req)
    assert result is not None
    assert result.startswith("fp-")
    assert len(result) == 3 + 64  # "fp-" + sha256 hex


# ---------------------------------------------------------------------------
# _get_or_create_device_user_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_device_user_id_creates_new_user(session: AsyncSession):
    req = _mock_request(headers={"X-Device-Fingerprint": "test-fp-new"})
    user_id = await _get_or_create_device_user_id(req, session)
    assert isinstance(user_id, uuid.UUID)


@pytest.mark.asyncio
async def test_get_or_create_device_user_id_reuses_existing(session: AsyncSession):
    req = _mock_request(headers={"X-Device-Fingerprint": "test-fp-reuse"})
    uid1 = await _get_or_create_device_user_id(req, session)
    uid2 = await _get_or_create_device_user_id(req, session)
    assert uid1 == uid2


@pytest.mark.asyncio
async def test_get_or_create_device_user_id_updates_existing_device(session: AsyncSession):
    """Second call with the same fingerprint updates ip_hash / user_agent."""
    req1 = _mock_request(
        headers={"X-Device-Fingerprint": "test-fp-update", "User-Agent": "AgentA"},
        client_host="1.2.3.4",
    )
    req2 = _mock_request(
        headers={"X-Device-Fingerprint": "test-fp-update", "User-Agent": "AgentB"},
        client_host="5.6.7.8",
    )
    await _get_or_create_device_user_id(req1, session)
    uid = await _get_or_create_device_user_id(req2, session)
    assert isinstance(uid, uuid.UUID)


@pytest.mark.asyncio
async def test_get_or_create_device_user_id_no_fingerprint_raises(session: AsyncSession):
    req = _mock_request()  # empty headers/cookies → no fingerprint
    with pytest.raises(HTTPException) as exc_info:
        await _get_or_create_device_user_id(req, session)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user_id — Bearer token path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_id_bearer_token(session: AsyncSession):
    user = await register_user(session, "bearer@test.com", "pass")
    await session.flush()
    token = create_access_token(user.id)
    req = _mock_request(headers={"Authorization": f"Bearer {token}"})
    uid = await get_current_user_id(request=req, session=session, access_token=None)
    assert uid == user.id


@pytest.mark.asyncio
async def test_get_current_user_id_invalid_token_raises(session: AsyncSession):
    req = _mock_request(headers={"Authorization": "Bearer invalid.token.here"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(request=req, session=session, access_token="invalid.token.here")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — inactive user path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_inactive_raises(session: AsyncSession):
    user = await register_user(session, "inactive@test.com", "pass")
    user.is_active = False
    session.add(user)
    await session.flush()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(user_id=user.id, session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_raises(session: AsyncSession):
    phantom_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(user_id=phantom_id, session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_returns_active_user(session: AsyncSession):
    user = await register_user(session, "active@test.com", "pass")
    await session.flush()
    result = await get_current_user(user_id=user.id, session=session)
    assert result.id == user.id
