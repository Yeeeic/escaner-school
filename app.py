from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from database.database import SessionLocal, init_db
from database.migrations import apply_compatible_migrations
from database.models import Device
from routes import admin, api, days, personnel, records, scanner, students
from services.day_service import ensure_today_operation


def configure_logging() -> None:
    handler = RotatingFileHandler(settings.LOG_DIR / "smart_access.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(item, RotatingFileHandler) for item in root.handlers):
        root.addHandler(handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    init_db()
    apply_compatible_migrations()
    with SessionLocal() as db:
        device = db.scalar(select(Device).where(Device.identificador == settings.DEVICE_IDENTIFIER))
        if not device:
            db.add(Device(nombre="Kiosco principal", ubicacion="Entrada principal",
                          identificador=settings.DEVICE_IDENTIFIER, activo=True))
            db.commit()
        ensure_today_operation(db)
    yield


app = FastAPI(title=settings.APP_NAME, version="7.0.0", lifespan=lifespan,
              docs_url="/api/docs" if settings.APP_ENV != "production" else None)
app.add_middleware(
    SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="sau_session",
    max_age=8 * 60 * 60, same_site="lax", https_only=settings.SESSION_HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
app.include_router(scanner.router)
app.include_router(admin.router)
app.include_router(students.router)
app.include_router(personnel.router)
app.include_router(records.router)
app.include_router(days.router)
app.include_router(api.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob:; connect-src 'self'; media-src 'self' blob:"
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Error no controlado en %s", request.url.path, exc_info=exc)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Ocurrió un error temporal. Intenta nuevamente."}, status_code=500)
    return JSONResponse({"detail": "Ocurrió un error temporal. Revisa logs/smart_access.log."}, status_code=500)


if __name__ == "__main__":
    uvicorn.run("app:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
