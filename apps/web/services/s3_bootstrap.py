from __future__ import annotations

import logging

from apps.web.config import settings
from packages.integrations.s3_storage import get_s3_client

logger = logging.getLogger(__name__)


def ensure_bucket_exists() -> None:
    if not settings.s3_endpoint:
        # AWS/prod manages buckets out of band.
        return
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        logger.info("Creating missing S3 bucket %s", settings.s3_bucket)
        client.create_bucket(Bucket=settings.s3_bucket)
