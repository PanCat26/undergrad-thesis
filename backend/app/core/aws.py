from typing import Any

import boto3

from app.config import Settings


def boto3_client(service: str, settings: Settings) -> Any:
    """Build a boto3 client, using static keys only when both are configured.

    When the keys are absent (the prod default), they're omitted so boto3 resolves credentials via
    its default chain — i.e. the EC2 instance role — instead of trying to use empty credentials.
    """
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service, **kwargs)
