from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class S3Client(Protocol):
    def put_object(self, **kwargs: object) -> object: ...

    def get_object(self, **kwargs: object) -> Mapping[str, S3ObjectBody]: ...

    def delete_object(self, **kwargs: object) -> object: ...


class S3ObjectBody(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...


class S3ObjectStorage:
    def __init__(self, client: S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata=dict(metadata or {}),
        )

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)