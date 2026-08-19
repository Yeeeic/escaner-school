from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    BASE_DIR = BASE_DIR
    APP_NAME = "Escáner School"
    APP_ENV = os.getenv("APP_ENV", "development")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    QR_SECRET_KEY = os.getenv("QR_SECRET_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'smart_access.db'}")
    ADMIN_INITIAL_PASSWORD = os.getenv("ADMIN_INITIAL_PASSWORD", "")
    ACCESS_COOLDOWN_SECONDS = int(os.getenv("ACCESS_COOLDOWN_SECONDS", "10"))
    TIMEZONE = os.getenv("TIMEZONE", "America/Mexico_City")
    DEVICE_IDENTIFIER = os.getenv("DEVICE_IDENTIFIER", "KIOSK-ENTRADA-01")
    _INSTITUTION_ENV = os.getenv("INSTITUTION_NAME", "").strip()
    INSTITUTION_NAME = ("Escáner School" if not _INSTITUTION_ENV or
                        _INSTITUTION_ENV == "Smart Access University" else _INSTITUTION_ENV)
    SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
    CAPACITY_LIMIT = int(os.getenv("CAPACITY_LIMIT", "500"))
    LONG_STAY_HOURS = int(os.getenv("LONG_STAY_HOURS", "10"))
    STUDENT_DEFAULT_VALIDITY_DAYS = int(os.getenv("STUDENT_DEFAULT_VALIDITY_DAYS", "365"))

    STATIC_DIR = BASE_DIR / "static"
    UPLOAD_DIR = STATIC_DIR / "uploads"
    QR_DIR = BASE_DIR / "qrcodes"
    REPORT_DIR = BASE_DIR / "reports"
    LOG_DIR = BASE_DIR / "logs"

    @classmethod
    def validate(cls) -> None:
        if cls.APP_ENV == "production":
            missing = [name for name in ("SECRET_KEY", "QR_SECRET_KEY") if not getattr(cls, name)]
            if missing:
                raise RuntimeError(f"Faltan variables críticas: {', '.join(missing)}")

        # Claves de desarrollo seguras para ejecución local; producción exige .env.
        cls.SECRET_KEY = cls.SECRET_KEY or "dev-session-key-change-in-env-9f48fef4"
        cls.QR_SECRET_KEY = cls.QR_SECRET_KEY or "dev-qr-key-change-in-env-f1d27c9a"
        for directory in (cls.UPLOAD_DIR, cls.QR_DIR, cls.REPORT_DIR, cls.LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.validate()
