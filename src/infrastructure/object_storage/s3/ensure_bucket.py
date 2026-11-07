import logging

from botocore.exceptions import ClientError

from api.settings import Settings
from infrastructure.object_storage.s3.client import create_s3_client


logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()
    s3_client = create_s3_client(settings)

    try:
        s3_client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        s3_client.create_bucket(Bucket=settings.s3_bucket)
        logger.info("Created object storage bucket %s", settings.s3_bucket)
    else:
        logger.info("Object storage bucket %s already exists", settings.s3_bucket)


if __name__ == "__main__":
    main()
