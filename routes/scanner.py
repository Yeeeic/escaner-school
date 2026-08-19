from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import settings
from security import get_csrf_token


router = APIRouter()
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))


@router.get("/", response_class=HTMLResponse)
def scanner_page(request: Request):
    return templates.TemplateResponse(request, "scanner.html", {
        "institution": settings.INSTITUTION_NAME,
        "cooldown": settings.ACCESS_COOLDOWN_SECONDS,
        "csrf_token": get_csrf_token(request),
    })


@router.get("/kiosk", response_class=HTMLResponse)
def kiosk_page(request: Request):
    return templates.TemplateResponse(request, "scanner.html", {
        "institution": settings.INSTITUTION_NAME,
        "cooldown": settings.ACCESS_COOLDOWN_SECONDS,
        "csrf_token": get_csrf_token(request),
        "kiosk": True,
    })
