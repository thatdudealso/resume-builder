from __future__ import annotations

import boto3
from botocore.client import Config

from apps.web.config import settings


def get_s3_client():
    kwargs: dict = {"region_name": settings.s3_region}
    if settings.s3_endpoint:
        kwargs["endpoint_url"] = settings.s3_endpoint
        kwargs["config"] = Config(signature_version="s3v4")
    if settings.s3_access_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key
        kwargs["aws_secret_access_key"] = settings.s3_secret_key
    return boto3.client("s3", **kwargs)


def upload_bytes(key: str, data: bytes, content_type: str) -> str:
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=settings.s3_object_key(key),
        Body=data,
        ContentType=content_type,
    )
    return key


def download_bytes(key: str) -> bytes:
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=settings.s3_object_key(key))
    return response["Body"].read()


def presigned_url(key: str, expires: int = 3600) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": settings.s3_object_key(key)},
        ExpiresIn=expires,
    )
