from __future__ import annotations

import pytest

from apps.web.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_endpoint(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_root_redirects_to_app_ui(app):
    """Public domain root must not return FastAPI JSON 404; send browsers to NiceGUI."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/", follow_redirects=False)
        assert r.status_code in (301, 302, 303, 307, 308)
        assert r.headers["location"] == "/app/"
        assert r.content != b'{"detail":"Not Found"}'
