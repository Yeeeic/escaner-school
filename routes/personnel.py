from __future__ import annotations

import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from config import settings
from database.database import get_db
from database.models import AuthorizedPersonnel
from routes.students import _clean, _save_photo
from security import get_csrf_token, validate_csrf
from services.access_service import local_now
from services.audit_service import record_audit
from services.credential_service import create_credential_pdf
from services.qr_service import generate_personnel_qr


router = APIRouter(prefix="/admin/personnel")
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))
PERSONNEL_TYPES = ("DOCENTE", "ADMINISTRATIVO", "SEGURIDAD", "DIRECTIVO", "SERVICIOS", "VISITANTE AUTORIZADO")


def _admin(request: Request):
    return request.session.get("admin")


def _context(request: Request, *, person=None, error=None):
    return {"admin": _admin(request), "person": person, "error": error, "types": PERSONNEL_TYPES,
            "default_expiry": date.today() + timedelta(days=settings.STUDENT_DEFAULT_VALIDITY_DAYS),
            "csrf_token": get_csrf_token(request), "active_page": "personnel"}


@router.get("", response_class=HTMLResponse)
def personnel_list(request: Request, q: str = "", tipo: str = "", papelera: str = "",
                   db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    in_trash = papelera == "1"
    query = select(AuthorizedPersonnel).where(AuthorizedPersonnel.eliminado.is_(in_trash))
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(AuthorizedPersonnel.numero_empleado.ilike(term),
                                AuthorizedPersonnel.nombres.ilike(term),
                                AuthorizedPersonnel.apellido_paterno.ilike(term),
                                AuthorizedPersonnel.apellido_materno.ilike(term)))
    if tipo:
        query = query.where(AuthorizedPersonnel.tipo_personal == tipo)
    people = db.scalars(query.order_by(AuthorizedPersonnel.tipo_personal,
                                       AuthorizedPersonnel.apellido_paterno)).all()
    return templates.TemplateResponse(request, "personnel.html", {
        **_context(request), "people": people, "filters": {"q": q, "tipo": tipo},
        "in_trash": in_trash, "today": date.today(),
        "trash_count": db.scalar(select(func.count(AuthorizedPersonnel.id)).where(
            AuthorizedPersonnel.eliminado.is_(True))) or 0,
    })


@router.get("/new", response_class=HTMLResponse)
def personnel_new(request: Request):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "personnel_form.html", _context(request))


@router.post("/new")
async def personnel_create(
    request: Request, numero_empleado: str = Form(...), nombres: str = Form(...),
    apellido_paterno: str = Form(...), apellido_materno: str = Form(""),
    tipo_personal: str = Form(...), area: str = Form(""), plantel: str = Form(...),
    turno: str = Form(...), fecha_vencimiento: date = Form(...), activo: bool = Form(False),
    csrf_token: str = Form(...), photo: UploadFile | None = File(None), db: Session = Depends(get_db),
):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    number = _clean(numero_empleado, 32)
    if db.scalar(select(AuthorizedPersonnel).where(AuthorizedPersonnel.numero_empleado == number)):
        return templates.TemplateResponse(request, "personnel_form.html",
            _context(request, error="El número de empleado ya existe."), status_code=422)
    try:
        person = AuthorizedPersonnel(
            personnel_id=f"SAU-PER-{secrets.token_hex(8)}", numero_empleado=number,
            nombres=_clean(nombres, 120), apellido_paterno=_clean(apellido_paterno, 80),
            apellido_materno=_clean(apellido_materno, 80),
            tipo_personal=tipo_personal if tipo_personal in PERSONNEL_TYPES else "DOCENTE",
            area=_clean(area, 160), plantel=_clean(plantel, 120), turno=_clean(turno, 40),
            fecha_vencimiento=fecha_vencimiento, activo=activo, foto=await _save_photo(photo),
        )
        db.add(person)
        db.commit()
        db.refresh(person)
        generate_personnel_qr(person.id, db)
        return RedirectResponse(f"/admin/personnel/{person.id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(request, "personnel_form.html",
            _context(request, error=str(exc)), status_code=422)


@router.post("/bulk")
def personnel_bulk(request: Request, action: str = Form(...), ids: list[int] = Form(default=[]),
                   csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    restore = action == "restore"
    for person in db.scalars(select(AuthorizedPersonnel).where(
            AuthorizedPersonnel.id.in_(ids[:500]))).all():
        if restore and person.eliminado:
            person.eliminado, person.deleted_at, person.deleted_by = False, None, None
            record_audit(db, admin["id"], "RESTAURAR", "PERSONAL", person.id, person.numero_empleado)
        elif not restore and action == "delete" and not person.eliminado:
            person.eliminado, person.activo = True, False
            person.deleted_at, person.deleted_by = local_now(), admin["id"]
            record_audit(db, admin["id"], "BORRAR", "PERSONAL", person.id, person.numero_empleado)
    db.commit()
    return RedirectResponse(f"/admin/personnel{'?papelera=1' if restore else ''}", status_code=303)


@router.get("/{person_id}", response_class=HTMLResponse)
def personnel_detail(person_id: int, request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    person = db.get(AuthorizedPersonnel, person_id)
    if not person:
        return RedirectResponse("/admin/personnel", status_code=303)
    return templates.TemplateResponse(request, "personnel_detail.html", {
        **_context(request, person=person),
        "qr_exists": (settings.QR_DIR / f"personal-{person.numero_empleado}.png").exists(),
    })


@router.get("/{person_id}/edit", response_class=HTMLResponse)
def personnel_edit(person_id: int, request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    person = db.get(AuthorizedPersonnel, person_id)
    if not person or person.eliminado:
        return RedirectResponse("/admin/personnel", status_code=303)
    return templates.TemplateResponse(request, "personnel_form.html", _context(request, person=person))


@router.post("/{person_id}/edit")
async def personnel_update(
    person_id: int, request: Request, numero_empleado: str = Form(...), nombres: str = Form(...),
    apellido_paterno: str = Form(...), apellido_materno: str = Form(""),
    tipo_personal: str = Form(...), area: str = Form(""), plantel: str = Form(...),
    turno: str = Form(...), fecha_vencimiento: date = Form(...), activo: bool = Form(False),
    csrf_token: str = Form(...), photo: UploadFile | None = File(None), db: Session = Depends(get_db),
):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    person = db.get(AuthorizedPersonnel, person_id)
    if not person or person.eliminado:
        return RedirectResponse("/admin/personnel", status_code=303)
    number = _clean(numero_empleado, 32)
    if db.scalar(select(AuthorizedPersonnel).where(
            AuthorizedPersonnel.numero_empleado == number, AuthorizedPersonnel.id != person.id)):
        return templates.TemplateResponse(request, "personnel_form.html",
            _context(request, person=person, error="El número de empleado ya existe."), status_code=422)
    try:
        old_qr = settings.QR_DIR / f"personal-{person.numero_empleado}.png"
        person.numero_empleado, person.nombres = number, _clean(nombres, 120)
        person.apellido_paterno, person.apellido_materno = _clean(apellido_paterno, 80), _clean(apellido_materno, 80)
        person.tipo_personal = tipo_personal if tipo_personal in PERSONNEL_TYPES else "DOCENTE"
        person.area, person.plantel, person.turno = _clean(area, 160), _clean(plantel, 120), _clean(turno, 40)
        person.fecha_vencimiento, person.activo = fecha_vencimiento, activo
        new_photo = await _save_photo(photo)
        if new_photo:
            person.foto = new_photo
        db.commit()
        if old_qr.name != f"personal-{person.numero_empleado}.png":
            old_qr.unlink(missing_ok=True)
        generate_personnel_qr(person.id, db)
        return RedirectResponse(f"/admin/personnel/{person.id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(request, "personnel_form.html",
            _context(request, person=person, error=str(exc)), status_code=422)


@router.post("/{person_id}/toggle")
def personnel_toggle(person_id: int, request: Request, csrf_token: str = Form(...),
                     db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    person = db.get(AuthorizedPersonnel, person_id)
    if person and not person.eliminado:
        person.activo = not person.activo
        db.commit()
    return RedirectResponse(f"/admin/personnel/{person_id}", status_code=303)


@router.post("/{person_id}/delete")
def personnel_delete(person_id: int, request: Request, csrf_token: str = Form(...),
                     db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    person = db.get(AuthorizedPersonnel, person_id)
    if person and not person.eliminado:
        person.eliminado, person.activo = True, False
        person.deleted_at, person.deleted_by = local_now(), admin["id"]
        record_audit(db, admin["id"], "BORRAR", "PERSONAL", person.id, person.numero_empleado)
        db.commit()
    return RedirectResponse("/admin/personnel", status_code=303)


@router.post("/{person_id}/restore")
def personnel_restore(person_id: int, request: Request, csrf_token: str = Form(...),
                      db: Session = Depends(get_db)):
    admin = _admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    person = db.get(AuthorizedPersonnel, person_id)
    if person and person.eliminado:
        person.eliminado, person.deleted_at, person.deleted_by = False, None, None
        record_audit(db, admin["id"], "RESTAURAR", "PERSONAL", person.id, person.numero_empleado)
        db.commit()
    return RedirectResponse("/admin/personnel?papelera=1", status_code=303)


@router.post("/{person_id}/qr")
def personnel_regenerate_qr(person_id: int, request: Request, csrf_token: str = Form(...),
                            db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    person = db.get(AuthorizedPersonnel, person_id)
    if person and not person.eliminado:
        generate_personnel_qr(person.id, db, rotate=True)
    return RedirectResponse(f"/admin/personnel/{person_id}", status_code=303)


@router.get("/{person_id}/qr")
def personnel_download_qr(person_id: int, request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    person = db.get(AuthorizedPersonnel, person_id)
    if not person or person.eliminado:
        return RedirectResponse("/admin/personnel", status_code=303)
    path = settings.QR_DIR / f"personal-{person.numero_empleado}.png"
    if not path.exists():
        path = generate_personnel_qr(person.id, db)
    return FileResponse(path, media_type="image/png", filename=f"QR-PERSONAL-{person.numero_empleado}.png")


@router.get("/{person_id}/credential")
def personnel_download_credential(person_id: int, request: Request, db: Session = Depends(get_db)):
    if not _admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    person = db.get(AuthorizedPersonnel, person_id)
    if not person or person.eliminado:
        return RedirectResponse("/admin/personnel", status_code=303)
    qr_path = settings.QR_DIR / f"personal-{person.numero_empleado}.png"
    if not qr_path.exists():
        qr_path = generate_personnel_qr(person.id, db)
    return Response(create_credential_pdf(person, qr_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Credencial-{person.numero_empleado}.pdf"'})
