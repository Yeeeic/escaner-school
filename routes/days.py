from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from config import settings
from database.database import get_db
from database.models import AccessRecord, DailyOperation
from security import get_csrf_token, validate_csrf
from services.access_service import local_now
from services.audit_service import record_audit
from services.day_service import (close_operation, ensure_today_operation, operation_summary,
                                  reopen_operation)


router = APIRouter(prefix="/admin/days")
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))


def _admin(request: Request):
    return request.session.get("admin")


@router.get("", response_class=HTMLResponse)
def days_page(request: Request, papelera: str = "", db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    current = ensure_today_operation(db, admin["id"])
    in_trash = papelera == "1"
    operations = db.scalars(select(DailyOperation).where(
        DailyOperation.eliminado.is_(in_trash)
    ).order_by(DailyOperation.fecha.desc()).limit(365)).all()
    summaries = [operation_summary(db, item) for item in operations]
    return templates.TemplateResponse(request, "days.html", {
        "admin": admin, "current": operation_summary(db, current), "days": summaries,
        "in_trash": in_trash,
        "trash_count": db.scalar(select(func.count(DailyOperation.id)).where(
            DailyOperation.eliminado.is_(True))) or 0,
        "csrf_token": get_csrf_token(request), "active_page": "days",
    })


@router.get("/{operation_id}", response_class=HTMLResponse)
def day_detail(operation_id: int, request: Request, db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    operation = db.get(DailyOperation, operation_id)
    if not operation:
        return RedirectResponse("/admin/days", status_code=303)
    records = db.execute(select(AccessRecord).options(
        joinedload(AccessRecord.student), joinedload(AccessRecord.personnel)).where(
        AccessRecord.fecha == operation.fecha, AccessRecord.eliminado.is_(False)
    ).order_by(AccessRecord.datetime.desc())).scalars().unique().all()
    return templates.TemplateResponse(request, "day_detail.html", {
        "admin": admin, "day": operation_summary(db, operation), "records": records,
        "operation": operation, "csrf_token": get_csrf_token(request), "active_page": "days",
    })


@router.post("/{operation_id}/close")
def close_day(operation_id: int, request: Request, note: str = Form(""), csrf_token: str = Form(...),
              db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    operation = db.get(DailyOperation, operation_id)
    current = ensure_today_operation(db, admin["id"])
    if operation and not operation.eliminado and operation.id == current.id:
        close_operation(db, operation, admin["id"], note)
    return RedirectResponse("/admin/days", status_code=303)


@router.post("/{operation_id}/reopen")
def reopen_day(operation_id: int, request: Request, note: str = Form(""), csrf_token: str = Form(...),
               db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    operation = db.get(DailyOperation, operation_id)
    current = ensure_today_operation(db, admin["id"])
    if operation and not operation.eliminado and operation.id == current.id:
        reopen_operation(db, operation, admin["id"], note)
    return RedirectResponse("/admin/days", status_code=303)


@router.post("/{operation_id}/delete")
def delete_day(operation_id: int, request: Request, csrf_token: str = Form(...),
               db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    operation = db.get(DailyOperation, operation_id)
    if operation and not operation.eliminado and operation.fecha != local_now().date():
        operation.eliminado = True
        operation.deleted_at = local_now()
        operation.deleted_by = admin["id"]
        record_audit(db, admin["id"], "BORRAR", "JORNADA", operation.id,
                     operation.fecha.isoformat())
        db.commit()
    return RedirectResponse("/admin/days", status_code=303)


@router.post("/bulk")
def days_bulk(request: Request, action: str = Form(...), ids: list[int] = Form(default=[]),
              csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    restore = action == "restore"
    today = local_now().date()
    for operation in db.scalars(select(DailyOperation).where(DailyOperation.id.in_(ids[:500]))).all():
        if restore and operation.eliminado:
            operation.eliminado, operation.deleted_at, operation.deleted_by = False, None, None
            record_audit(db, admin["id"], "RESTAURAR", "JORNADA", operation.id, operation.fecha.isoformat())
        elif action == "delete" and not operation.eliminado and operation.fecha != today:
            operation.eliminado, operation.deleted_at, operation.deleted_by = True, local_now(), admin["id"]
            record_audit(db, admin["id"], "BORRAR", "JORNADA", operation.id, operation.fecha.isoformat())
    db.commit()
    return RedirectResponse(f"/admin/days{'?papelera=1' if restore else ''}", status_code=303)


@router.post("/{operation_id}/restore")
def restore_day(operation_id: int, request: Request, csrf_token: str = Form(...),
                db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    operation = db.get(DailyOperation, operation_id)
    if operation and operation.eliminado:
        operation.eliminado = False
        operation.deleted_at = None
        operation.deleted_by = None
        record_audit(db, admin["id"], "RESTAURAR", "JORNADA", operation.id,
                     operation.fecha.isoformat())
        db.commit()
    return RedirectResponse("/admin/days?papelera=1", status_code=303)
