from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from apps.web.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_cognito_jwks() -> tuple[PyJWKClient | None, str | None]:
    if not settings.cognito_user_pool_id:
        return None, None
    issuer = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )
    return PyJWKClient(f"{issuer}/.well-known/jwks.json"), issuer


def decode_cognito_jwt(token: str) -> dict[str, Any] | None:
    """Validate a Cognito ID or access token against the configured user pool."""
    jwks_client, issuer = _get_cognito_jwks()
    if jwks_client is None or issuer is None:
        return None
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
        if payload.get("token_use") != "id":
            logger.warning("Rejecting Cognito token with token_use=%s", payload.get("token_use"))
            return None
        expected_client_id = (settings.cognito_app_client_id or "").strip() or None
        if expected_client_id:
            aud = payload.get("aud")
            if aud and aud != expected_client_id:
                logger.warning("Cognito token client id mismatch")
                return None
        if not payload.get("sub"):
            return None
        return payload
    except Exception as exc:
        logger.warning("Cognito JWT validation failed: %s", exc)
        return None


def clear_cognito_jwks_cache() -> None:
    """Test helper to reset the cached JWKS client."""
    _get_cognito_jwks.cache_clear()
