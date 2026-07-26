from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from apps.web.services.s3_bootstrap import ensure_bucket_exists


def _client_error(status: int) -> ClientError:
    return ClientError(
        {"Error": {"Code": str(status)}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "HeadBucket",
    )


def test_creates_bucket_when_missing():
    client = MagicMock()
    client.head_bucket.side_effect = _client_error(404)
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.env = "local"
        s.s3_endpoint = "http://minio:9000"
        s.s3_bucket = "resume-builder"
        ensure_bucket_exists()
    client.create_bucket.assert_called_once_with(Bucket="resume-builder")


def test_skips_when_no_endpoint():
    client = MagicMock()
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.env = "local"
        s.s3_endpoint = None
        ensure_bucket_exists()
    client.create_bucket.assert_not_called()


def test_does_not_create_on_access_denied():
    client = MagicMock()
    client.head_bucket.side_effect = _client_error(403)
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.env = "local"
        s.s3_endpoint = "http://minio:9000"
        s.s3_bucket = "resume-builder"
        ensure_bucket_exists()
    client.create_bucket.assert_not_called()


def test_connection_failure_does_not_create_or_raise():
    client = MagicMock()
    client.head_bucket.side_effect = OSError("connection refused")
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.env = "local"
        s.s3_endpoint = "http://minio:9000"
        s.s3_bucket = "resume-builder"
        ensure_bucket_exists()
    client.create_bucket.assert_not_called()


def test_create_failure_does_not_abort_startup():
    client = MagicMock()
    client.head_bucket.side_effect = _client_error(404)
    client.create_bucket.side_effect = OSError("endpoint down")
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.env = "local"
        s.s3_endpoint = "http://minio:9000"
        s.s3_bucket = "resume-builder"
        ensure_bucket_exists()
    client.create_bucket.assert_called_once()


def test_skips_bootstrap_outside_local_and_dev():
    client = MagicMock()
    with patch("apps.web.services.s3_bootstrap.get_s3_client", return_value=client), \
         patch("apps.web.services.s3_bootstrap.settings") as s:
        s.env = "qa"
        s.s3_endpoint = "http://minio:9000"
        ensure_bucket_exists()
    client.head_bucket.assert_not_called()
    client.create_bucket.assert_not_called()
