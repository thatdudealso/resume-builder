from unittest.mock import MagicMock, patch

from apps.web.services.s3_bootstrap import ensure_bucket_exists


def test_creates_bucket_when_missing():
    client = MagicMock()
    client.head_bucket.side_effect = Exception("404")
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.s3_endpoint = "http://minio:9000"
        s.s3_bucket = "resume-builder"
        ensure_bucket_exists()
    client.create_bucket.assert_called_once_with(Bucket="resume-builder")


def test_skips_when_no_endpoint():
    client = MagicMock()
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.s3_endpoint = None
        ensure_bucket_exists()
    client.create_bucket.assert_not_called()
