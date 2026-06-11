"""
Application configuration — all environment variables via pydantic-settings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "Pharmacy Near-Expiry Marketplace"
    APP_ENV: str = "development"  # development | staging | production
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"

    # ── Server ───────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pharmacy_marketplace"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    # ── JWT ──────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-jwt-secret-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Security Guards ───────────────────────────────────────────────────
    REQUIRE_CLOUDFLARE: bool = False   # Enforce CF-Connecting-IP header
    REQUIRE_APPCHECK: bool = False     # Enforce Firebase App Check token

    # ── Firebase App Check ────────────────────────────────────────────────
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_APP_CHECK_PUBLIC_KEYS_URL: str = (
        "https://firebaseappcheck.googleapis.com/v1/jwks"
    )

    # ── Cloudflare ────────────────────────────────────────────────────────
    CLOUDFLARE_ALLOWED_IPS: str = ""  # comma-separated CIDR list; empty = any

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    NOLOG: bool = False  # Set True to suppress all application logs

    # ── File Storage ──────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"    # local | s3
    STORAGE_LOCAL_PATH: str = "/tmp/uploads"
    AWS_S3_BUCKET: str = ""
    AWS_S3_REGION: str = "me-south-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Email (Resend / SMTP stub) ────────────────────────────────────────
    EMAIL_BACKEND: str = "stub"       # stub | resend | smtp
    RESEND_API_KEY: str = ""
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@pharmacy-marketplace.sa"

    # ── WhatsApp (Meta Cloud API stub) ────────────────────────────────────
    WHATSAPP_BACKEND: str = "stub"    # stub | meta
    META_WHATSAPP_ACCESS_TOKEN: str = ""
    META_WHATSAPP_PHONE_NUMBER_ID: str = ""

    # ── Scheduler ────────────────────────────────────────────────────────
    NEAR_EXPIRY_SCAN_INTERVAL_HOURS: int = 6
    NEAR_EXPIRY_THRESHOLDS_DAYS: str = "180,90,30"

    @property
    def near_expiry_thresholds(self) -> List[int]:
        return [int(d.strip()) for d in self.NEAR_EXPIRY_THRESHOLDS_DAYS.split(",")]

    # ── Frontend URL (for emails/links) ──────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
