from __future__ import annotations

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from config import settings
from database.database import get_db
from database.models import AccessRecord, Administrator, Student
from security import get_csrf_token, validate_csrf, verify_password
from services.access_service import get_people_inside, local_now, recent_access, today_stats
from services.day_service import ensure_today_operation, operational_alerts, operation_summary


router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))


def _admin(request: Request):
    return request.session.get("admin")


def _chart_period(period: str, today: date) -> tuple[date, date, str]:
    if period == "day":
        return today, today, "Día"
    if period == "month":
        start = today.replace(day=1)
        return start, today.replace(day=calendar.monthrange(today.year, today.month)[1]), "Mes"
    if period == "year":
        return date(today.year, 1, 1), date(today.year, 12, 31), "Año"
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6), "Semana"


def _build_chart_data(db: Session, period: str = "week", career: str = "") -> dict:
    today = local_now().date()
    period = period if period in {"day", "week", "month", "year"} else "week"
    start, end, period_label = _chart_period(period, today)
    base_filters = [AccessRecord.fecha >= start, AccessRecord.fecha <= end,
                    AccessRecord.resultado == "AUTORIZADO", AccessRecord.eliminado.is_(False)]
    movement_query = select(AccessRecord)
    if career:
        movement_query = movement_query.join(Student).where(
            Student.carrera == career, Student.eliminado.is_(False))
    movement_query = movement_query.where(*base_filters)

    if period == "day":
        bucket = func.strftime("%H", AccessRecord.datetime)
        labels = [f"{hour:02d}:00" for hour in range(24)]
        keys = [f"{hour:02d}" for hour in range(24)]
    elif period == "year":
        bucket = func.strftime("%m", AccessRecord.fecha)
        labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        keys = [f"{month:02d}" for month in range(1, 13)]
    else:
        bucket = AccessRecord.fecha
        total_days = (end - start).days + 1
        keys = [start + timedelta(days=index) for index in range(total_days)]
        labels = [item.strftime("%d/%m") for item in keys]
    rows = db.execute(movement_query.with_only_columns(
        bucket, AccessRecord.tipo_movimiento, func.count(AccessRecord.id)
    ).group_by(bucket, AccessRecord.tipo_movimiento).order_by(bucket)).all()
    movement_map = {(row[0], row[1]): row[2] for row in rows}

    career_query = (select(Student.carrera, func.count(AccessRecord.id)).join(
        AccessRecord, AccessRecord.student_id == Student.id).where(
        *base_filters, AccessRecord.tipo_movimiento == "ENTRADA", Student.eliminado.is_(False)))
    if career:
        career_query = career_query.where(Student.carrera == career)
    career_rows = db.execute(career_query.group_by(Student.carrera).order_by(
        func.count(AccessRecord.id).desc()).limit(12)).all()
    return {
        "period": period, "period_label": period_label, "start": start.isoformat(), "end": end.isoformat(),
        "selected_career": career, "labels": labels,
        "entries": [movement_map.get((key, "ENTRADA"), 0) for key in keys],
        "exits": [movement_map.get((key, "SALIDA"), 0) for key in keys],
        "careers": [row[0] for row in career_rows], "career_values": [row[1] for row in career_rows],
    }


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"csrf_token": get_csrf_token(request)})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          csrf_token: str = Form(...), db: Session = Depends(get_db)):
    validate_csrf(request, csrf_token)
    admin = db.scalar(select(Administrator).where(Administrator.username == username.strip().lower()))
    if not admin or not admin.activo or not verify_password(password, admin.password_hash):
        return templates.TemplateResponse(request, "login.html", {
            "csrf_token": get_csrf_token(request), "error": "Usuario o contraseña incorrectos."
        }, status_code=401)
    request.session.clear()
    request.session["admin"] = {"id": admin.id, "username": admin.username, "name": admin.nombre, "role": admin.rol}
    get_csrf_token(request)
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    stats = today_stats(db)
    stats["students"] = db.scalar(select(func.count(Student.id)).where(
        Student.activo.is_(True), Student.eliminado.is_(False))) or 0
    now = local_now()
    operation = ensure_today_operation(db, admin["id"])
    alerts = operational_alerts(db)
    hourly_rows = db.execute(
        select(func.strftime("%H", AccessRecord.datetime), func.count(AccessRecord.id))
        .where(AccessRecord.fecha == now.date(), AccessRecord.tipo_movimiento == "ENTRADA",
               AccessRecord.resultado == "AUTORIZADO", AccessRecord.eliminado.is_(False))
        .group_by(func.strftime("%H", AccessRecord.datetime))
    ).all()
    chart = _build_chart_data(db)
    hour_map = {row[0]: row[1] for row in hourly_rows}
    chart["hours"] = [f"{hour:02d}:00" for hour in range(6, 23)]
    chart["entries_by_hour"] = [hour_map.get(f"{hour:02d}", 0) for hour in range(6, 23)]
    career_options = db.scalars(select(Student.carrera).where(
        Student.eliminado.is_(False)).distinct().order_by(Student.carrera)).all()
    return templates.TemplateResponse(request, "dashboard.html", {
        "admin": admin, "stats": stats, "recent": recent_access(db, 10), "chart": chart,
        "operation": operation_summary(db, operation), "alerts": alerts, "career_options": career_options,
        "csrf_token": get_csrf_token(request), "active_page": "dashboard",
    })


@router.get("/charts/data")
def dashboard_chart_data(request: Request, period: str = "week", career: str = "",
                         db: Session = Depends(get_db)):
    if not _admin(request):
        return {"error": "Inicia sesión"}
    available = set(db.scalars(select(Student.carrera).where(Student.eliminado.is_(False)).distinct()).all())
    return _build_chart_data(db, period, career if career in available else "")
