import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _database_url() -> str:
    """Return Railway's PostgreSQL URL or a local SQLite fallback."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_path = os.getenv("DATABASE_PATH", str(BASE_DIR / "resume_analyzer.db"))
        return f"sqlite:///{database_path}"

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


class DevelopmentConfig:
    DEBUG = True
    TESTING = False
    DATA_BACKEND = os.getenv("DATA_BACKEND", "sqlalchemy").lower()
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5000,http://localhost:5000")


class ProductionConfig(DevelopmentConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}