from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.web.config import settings
from packages.integrations.s3_storage import download_bytes, upload_bytes


@patch("packages.integrations.s3_storage.get_s3_client")
def test_upload_applies_prefix(mock_client, monkeypatch):
    monkeypatch.setattr(settings, "s3_prefix", "resumebild")
    client = MagicMock()
    mock_client.return_value = client
    key = upload_bytes("path/file.txt", b"data", "text/plain")
    assert key == "path/file.txt"
    assert client.put_object.call_args.kwargs["Key"] == "resumebild/path/file.txt"


@patch("packages.integrations.s3_storage.get_s3_client")
def test_download_applies_prefix(mock_client, monkeypatch):
    monkeypatch.setattr(settings, "s3_prefix", "resumebild/")
    client = MagicMock()
    client.get_object.return_value = {"Body": MagicMock(read=lambda: b"file-data")}
    mock_client.return_value = client
    assert download_bytes("path/file.txt") == b"file-data"
    assert client.get_object.call_args.kwargs["Key"] == "resumebild/path/file.txt"
