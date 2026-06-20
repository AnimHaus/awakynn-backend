from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    MONGODB_URL: str
    DB_NAME: str = "grabfabs"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ORIGINS: str = "http://localhost:3000"

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # R2 / S3-compatible storage
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_ACCOUNT_ID: str = ""
    # Public CDN base URL (e.g. https://pub-<id>.r2.dev)
    R2_ENDPOINT_URL: str = ""

    # Per-brand bucket names — empty means that brand's bucket isn't configured yet
    R2_BUCKET_GRABFABS: str = ""
    R2_BUCKET_AWAKYNN: str = ""
    R2_BUCKET_FESTIQ: str = ""
    R2_BUCKET_ESTRA: str = ""

    # Google Calendar / Meet
    GOOGLE_SERVICE_ACCOUNT_EMAIL: str = ""
    GOOGLE_PRIVATE_KEY: str = ""
    GOOGLE_CALENDAR_ID: str = "primary"

    @property
    def r2_api_endpoint(self) -> str:
        """S3-compatible API endpoint used for uploads (different from the public CDN URL)."""
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    @property
    def r2_bucket_map(self) -> dict[str, str]:
        """Map of brand slug → bucket name. Only includes configured brands."""
        mapping = {
            "grabfabs": self.R2_BUCKET_GRABFABS,
            "awakynn": self.R2_BUCKET_AWAKYNN,
            "festiq": self.R2_BUCKET_FESTIQ,
            "estra": self.R2_BUCKET_ESTRA,
        }
        return {brand: bucket for brand, bucket in mapping.items() if bucket}

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
