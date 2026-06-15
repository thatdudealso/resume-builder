from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.web.config import settings
from packages.integrations.s3_storage import get_s3_client


@patch("packages.integrations.s3_storage.boto3.client")
def test_get_s3_client_with_endpoint(mock_boto):
    mock_boto.return_value = MagicMock()
    with patch.object(settings, "s3_endpoint", "http://minio:9000"):
        with patch.object(settings, "s3_access_key", "key"):
            with patch.object(settings, "s3_secret_key", "secret"):
                client = get_s3_client()
                assert client is not None
