import boto3
from botocore.client import BaseClient
from botocore.config import Config

from api.settings import Settings


def create_s3_client(settings: Settings) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=str(settings.s3_endpoint_url),
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )
