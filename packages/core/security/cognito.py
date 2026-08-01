from __future__ import annotations

import json
import logging
import socket
import ssl
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient

from apps.web.config import settings

logger = logging.getLogger(__name__)


def _fetch_json_ipv4(url: str, timeout: float = 10.0) -> dict[str, Any]:
    """HTTP GET JSON forcing IPv4 (App Runner VPC egress commonly lacks IPv6)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    addr = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4]
    context = ssl.create_default_context()
    with socket.create_connection(addr, timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as sock:
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "Connection: close\r\n"
                "Accept: application/json\r\n"
                "\r\n"
            )
            sock.sendall(req.encode())
            chunks: list[bytes] = []
            while True:
                data = sock.recv(8192)
                if not data:
                    break
                chunks.append(data)
    raw_response = b"".join(chunks)
    header_blob, _, body = raw_response.partition(b"\r\n\r\n")
    status_line = header_blob.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
    if " 200 " not in f" {status_line} " and not status_line.endswith(" 200"):
        # Accept "HTTP/1.1 200 OK"
        if " 200" not in status_line:
            raise RuntimeError(f"JWKS fetch failed: {status_line}")
    return json.loads(body.decode())


class _IPv4PyJWKClient(PyJWKClient):
    def fetch_data(self) -> Any:  # type: ignore[override]
        return _fetch_json_ipv4(self.uri)


@lru_cache(maxsize=1)
def _get_cognito_jwks() -> tuple[PyJWKClient | None, str | None]:
    if not settings.cognito_user_pool_id:
        return None, None
    issuer = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )
    return _IPv4PyJWKClient(f"{issuer}/.well-known/jwks.json"), issuer


def decode_cognito_jwt(token: str) -> dict[str, Any] | None:
    """Validate a Cognito ID token against the configured user pool."""
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
