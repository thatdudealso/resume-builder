from __future__ import annotations

import socket

from packages.core.security.cognito import _fetch_json_ipv4


def test_fetch_jwks_forces_ipv4_and_preserves_tls_host(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSocket:
        response_chunks = [
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"keys\": []}",
            b"",
        ]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def sendall(self, data: bytes) -> None:
            calls["request"] = data

        def recv(self, _size: int) -> bytes:
            return self.response_chunks.pop(0)

    class FakeTlsContext:
        def wrap_socket(self, raw, *, server_hostname: str):
            assert isinstance(raw, FakeSocket)
            calls["server_hostname"] = server_hostname
            return raw

    def fake_getaddrinfo(host, port, family, socktype):
        calls["address_lookup"] = (host, port, family, socktype)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.51.100.7", port))]

    def fake_create_connection(address, *, timeout):
        calls["connection"] = (address, timeout)
        return FakeSocket()

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    monkeypatch.setattr(
        "packages.core.security.cognito.ssl.create_default_context",
        lambda: FakeTlsContext(),
    )

    assert _fetch_json_ipv4(
        "https://cognito.example/.well-known/jwks.json?pool=prod"
    ) == {"keys": []}
    assert calls["address_lookup"] == (
        "cognito.example",
        443,
        socket.AF_INET,
        socket.SOCK_STREAM,
    )
    assert calls["connection"] == (("198.51.100.7", 443), 10.0)
    assert calls["server_hostname"] == "cognito.example"
    assert b"Host: cognito.example\r\n" in calls["request"]
    assert b"GET /.well-known/jwks.json?pool=prod HTTP/1.1\r\n" in calls["request"]
