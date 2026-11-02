from collections.abc import Mapping
from io import BytesIO

from infrastructure.object_storage.s3.storage import S3ObjectStorage


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def put_object(self, **kwargs: object) -> object:
        self.calls.append(("put_object", kwargs))
        return {}

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        self.calls.append(("get_object", kwargs))
        return {"Body": BytesIO(b"matrix")}

    def delete_object(self, **kwargs: object) -> object:
        self.calls.append(("delete_object", kwargs))
        return {}


def test_s3_object_storage_uses_bucket_and_preserves_metadata() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(client, "paretolab-local")

    storage.put(
        "uploads/opaque-key",
        b"matrix",
        "text/csv",
        {"sha256": "abc123"},
    )

    assert client.calls == [
        (
            "put_object",
            {
                "Bucket": "paretolab-local",
                "Key": "uploads/opaque-key",
                "Body": b"matrix",
                "ContentType": "text/csv",
                "Metadata": {"sha256": "abc123"},
            },
        )
    ]


def test_s3_object_storage_reads_and_deletes_objects() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(client, "paretolab-local")

    assert storage.get("uploads/opaque-key") == b"matrix"
    storage.delete("uploads/opaque-key")

    assert client.calls == [
        ("get_object", {"Bucket": "paretolab-local", "Key": "uploads/opaque-key"}),
        ("delete_object", {"Bucket": "paretolab-local", "Key": "uploads/opaque-key"}),
    ]