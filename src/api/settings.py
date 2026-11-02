from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_environment: Literal["development", "test", "production"] = "development"
    database_url: str = Field(min_length=1)
    celery_broker_url: str = Field(min_length=1)
    s3_endpoint_url: AnyHttpUrl
    s3_bucket: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$",
    )
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    temporary_upload_ttl_seconds: int = Field(default=3600, gt=0)
    default_page_size: int = Field(default=50, gt=0)
    maximum_page_size: int = Field(default=200, gt=0)
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=5000, ge=1, le=65535)

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if make_url(value).drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        return value

    @field_validator("maximum_page_size")
    @classmethod
    def maximum_page_size_must_cover_default(
        cls,
        value: int,
        info: ValidationInfo,
    ) -> int:
        default_page_size = info.data.get("default_page_size", 50)
        if value < default_page_size:
            raise ValueError("MAXIMUM_PAGE_SIZE must be at least DEFAULT_PAGE_SIZE")
        return value
