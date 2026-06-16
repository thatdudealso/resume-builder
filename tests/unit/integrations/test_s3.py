from __future__ import annotations

from unittest.mock import MagicMock, patch

from packages.integrations.s3_storage import presigned_url, upload_bytes


@patch("packages.integrations.s3_storage.get_s3_client")
def test_upload_bytes(mock_client):
    client = MagicMock()
    mock_client.return_value = client
    key = upload_bytes("path/file.txt", b"data", "text/plain")
    assert key == "path/file.txt"
    client.put_object.assert_called_once()


@patch("packages.integrations.s3_storage.get_s3_client")
def test_presigned_url(mock_client):
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://signed.url"
    mock_client.return_value = client
    url = presigned_url("path/file.txt")
    assert url == "https://signed.url"
