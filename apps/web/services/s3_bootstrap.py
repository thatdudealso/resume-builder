from __future__ import annotations

import logging

from botocore.exceptions import ClientError

from apps.web.config import settings
from packages.integrations.s3_storage import get_s3_client

logger = logging.getLogger(__name__)


def ensure_bucket_exists() -> None:
    if settings.env not in ("local", "dev") or not settings.s3_endpoint:
        # AWS/prod manages buckets out of band.
        return
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        return
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status not in (404, None):
            logger.warning(
                "S3 bucket %s exists but is not accessible (HTTP %s); skipping bootstrap.",
                settings.s3_bucket,
                status,
            )
            return
    except Exception:
        logger.warning(
            "Could not reach S3 endpoint %s to check bucket %s; skipping bootstrap.",
            settings.s3_endpoint,
            settings.s3_bucket,
            exc_info=True,
        )
        return

    logger.info("Creating missing S3 bucket %s", settings.s3_bucket)
    try:
        client.create_bucket(Bucket=settings.s3_bucket)
    except Exception:
        logger.warning(
            "Failed to create S3 bucket %s; continuing startup.",
            settings.s3_bucket,
            exc_info=True,
        )
