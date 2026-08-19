from __future__ import annotations

import math
from datetime import date, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from config import settings
from database.database import get_db
from database.models import AccessRecord, AuthorizedPersonnel, Student
from security import get_csrf_token, validate_csrf
from services.access_service import get_people_inside, grouped_people_inside, local_now
from services.audit_service import record_audit
from services.report_service import (create_csv, create_entries_csv, create_entries_excel,
                                     create_entries_pdf, create_excel, create_pdf, summarize_entries)


router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))


def _admin(request: Request):
    return request.session.get("admin")


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _filtered_query(params):
    in_trash = params.get("papelera", "") == "1"
    query = (select(AccessRecord).options(joinedload(AccessRecord.student), joinedload(AccessRecord.personnel))
             .outerjoin(Student).outerjoin(AuthorizedPersonnel)
             .where(AccessRecord.eliminado.is_(in_trash)))
    start = _parse_date(params.get("from", ""))
    end = _parse_date(params.get("to", ""))
    if start:
        query = query.where(AccessRecord.fecha >= start)
    if end:
        query = query.where(AccessRecord.fecha <= end)
    q = params.get("q", "").strip()
    if q:
        term = f"%{q}%"
        query = query.where(or_(Student.matricula.ilike(term), Student.nombres.ilike(term),
                                Student.apellido_paterno.ilike(term), Student.apellido_materno.ilike(term),
                                AuthorizedPersonnel.numero_empleado.ilike(term),
                                AuthorizedPersonnel.nombres.ilike(term),
                                AuthorizedPersonnel.apellido_paterno.ilike(term)))
    carrera = params.get("carrera", "")
    if carrera:
        query = query.where(Student.carrera == carrera)
    movement = params.get("movement", "")
    if movement in {"ENTRADA", "SALIDA"}:
        query = query.where(AccessRecord.tipo_movimiento == movement)
    result = params.get("result", "")
    if result in {"AUTORIZADO", "DENEGADO"}:
        query = query.where(AccessRecord.resultado == result)
    return query


@router.get("/records", response_class=HTMLResponse)
def records_page(request: Request, page: int = 1, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    page = max(page, 1)
    per_page = 20
    base = _filtered_query(request.query_params)
    count_query = select(func.count()).select_from(base.order_by(None).subquery())
    total = db.scalar(count_query) or 0
    records = db.execute(base.order_by(AccessRecord.datetime.desc()).offset((page - 1) * per_page).limit(per_page)).scalars().unique().all()
    careers = db.scalars(select(Student.carrera).where(Student.eliminado.is_(False)).distinct().order_by(Student.carrera)).all()
    filters = {key: request.query_params.get(key, "") for key in ("q", "from", "to", "carrera", "movement", "result", "papelera")}
    in_trash = filters["papelera"] == "1"
    entry_params = {**filters, "movement": "ENTRADA", "result": "AUTORIZADO", "papelera": ""}
    entry_records = db.execute(_filtered_query(entry_params).order_by(
        AccessRecord.datetime.desc()).limit(10000)).scalars().unique().all()
    entries_query = urlencode({key: value for key, value in entry_params.items() if value})
    base_quick = {key: filters[key] for key in ("q", "from", "to", "carrera") if filters[key]}
    def quick_query(**changes):
        values = {**base_quick, **changes}
        return urlencode({key: value for key, value in values.items() if value})
    today = local_now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    quick_queries = {
        "all": quick_query(),
        "entries": quick_query(movement="ENTRADA", result="AUTORIZADO"),
        "exits": quick_query(movement="SALIDA", result="AUTORIZADO"),
        "denied": quick_query(movement="", result="DENEGADO"),
        "today": quick_query(**{"from": today.isoformat(), "to": today.isoformat(),
                                 "movement": "ENTRADA", "result": "AUTORIZADO"}),
        "week": quick_query(**{"from": week_start.isoformat(), "to": today.isoformat(),
                                "movement": "ENTRADA", "result": "AUTORIZADO"}),
        "month": quick_query(**{"from": month_start.isoformat(), "to": today.isoformat(),
                                 "movement": "ENTRADA", "result": "AUTORIZADO"}),
    }
    return templates.TemplateResponse(request, "records.html", {
        "admin": _admin(request), "records": records, "careers": careers, "filters": filters,
        "page": page, "pages": max(1, math.ceil(total / per_page)), "total": total,
        "in_trash": in_trash,
        "entry_summary": summarize_entries(entry_records), "entries_query": entries_query,
        "quick_queries": quick_queries,
        "trash_count": db.scalar(select(func.count(AccessRecord.id)).where(AccessRecord.eliminado.is_(True))) or 0,
        "csrf_token": get_csrf_token(request), "active_page": "records",
    })


@router.post("/records/{record_id}/delete")
def delete_record(record_id: int, request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    record = db.get(AccessRecord, record_id)
    if record and not record.eliminado:
        record.eliminado = True
        record.deleted_at = local_now()
        record.deleted_by = admin["id"]
        record_audit(db, admin["id"], "BORRAR", "REGISTRO", record.id,
                     f"{record.fecha.isoformat()} · {record.tipo_movimiento or 'SIN MOVIMIENTO'} · {record.resultado}")
        db.commit()
    return RedirectResponse("/admin/records", status_code=303)


@router.post("/records/bulk")
def records_bulk(request: Request, action: str = Form(...), ids: list[int] = Form(default=[]),
                 csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    restore = action == "restore"
    for record in db.scalars(select(AccessRecord).where(AccessRecord.id.in_(ids[:500]))).all():
        if restore and record.eliminado:
            record.eliminado, record.deleted_at, record.deleted_by = False, None, None
            record_audit(db, admin["id"], "RESTAURAR", "REGISTRO", record.id, record.fecha.isoformat())
        elif action == "delete" and not record.eliminado:
            record.eliminado, record.deleted_at, record.deleted_by = True, local_now(), admin["id"]
            record_audit(db, admin["id"], "BORRAR", "REGISTRO", record.id, record.fecha.isoformat())
    db.commit()
    return RedirectResponse(f"/admin/records{'?papelera=1' if restore else ''}", status_code=303)


@router.post("/records/{record_id}/restore")
def restore_record(record_id: int, request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    record = db.get(AccessRecord, record_id)
    if record and record.eliminado:
        record.eliminado = False
        record.deleted_at = None
        record.deleted_by = None
        record_audit(db, admin["id"], "RESTAURAR", "REGISTRO", record.id,
                     record.fecha.isoformat())
        db.commit()
    return RedirectResponse("/admin/records?papelera=1", status_code=303)


@router.get("/records/export/{kind}")
def export_records(kind: str, request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    records = db.execute(_filtered_query(request.query_params).order_by(AccessRecord.datetime.desc()).limit(10000)).scalars().unique().all()
    if kind == "csv":
        return Response(create_csv(records), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=registros.csv"})
    if kind == "xlsx":
        return Response(create_excel(records), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=registros.xlsx"})
    if kind == "pdf":
        return Response(create_pdf(records), media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=reporte-accesos.pdf"})
    return Response("Formato no soportado", status_code=404)


@router.get("/records/entries/report/{kind}")
def export_entry_report(kind: str, request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    params = {key: request.query_params.get(key, "") for key in
              ("q", "from", "to", "carrera", "papelera")}
    params.update({"movement": "ENTRADA", "result": "AUTORIZADO", "papelera": ""})
    records = db.execute(_filtered_query(params).order_by(
        AccessRecord.datetime.desc()).limit(10000)).scalars().unique().all()
    if kind == "xlsx":
        return Response(create_entries_excel(records),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=reporte-entradas.xlsx"})
    if kind == "pdf":
        return Response(create_entries_pdf(records), media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=reporte-entradas.pdf"})
    if kind == "csv":
        return Response(create_entries_csv(records), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=reporte-entradas.csv"})
    return Response("Formato no soportado", status_code=404)


@router.get("/inside", response_class=HTMLResponse)
def inside_page(request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    groups = grouped_people_inside(db)
    return templates.TemplateResponse(request, "inside.html", {
        "admin": _admin(request), "people": groups["all"], "groups": groups,
        "csrf_token": get_csrf_token(request),
        "active_page": "inside",
    })


@router.get("/search")
def global_search(request: Request, q: str = ""):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return RedirectResponse(f"/admin/students?q={q}", status_code=303)
