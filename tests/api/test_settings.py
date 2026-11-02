import pytest
from pydantic import ValidationError

from api.settings import Settings


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://user:password@localhost/paretolab",
        "celery_broker_url": "redis://localhost:6379/0",
        "s3_endpoint_url": "http://localhost:9000",
        "s3_bucket": "paretolab-local",
        "s3_access_key": "local-access",
        "s3_secret_key": "local-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_apply_upload_and_pagination_defaults() -> None:
    settings = build_settings()

    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.temporary_upload_ttl_seconds == 3600
    assert settings.default_page_size == 50
    assert settings.maximum_page_size == 200
    assert settings.api_port == 5000


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_upload_bytes", 0),
        ("temporary_upload_ttl_seconds", 0),
        ("default_page_size", 0),
        ("maximum_page_size", 10),
        ("api_port", 70000),
        ("database_url", "sqlite:///local.db"),
    ],
)
def test_settings_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        build_settings(**{field: value})
