from __future__ import annotations

import io
import secrets
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from config import settings
from database.database import get_db
from database.models import Student
from security import get_csrf_token, validate_csrf
from services.qr_service import generate_student_qr
from services.student_import_service import process_student_file, sample_csv, suggest_next_matricula
from services.access_service import local_now
from services.audit_service import record_audit
from services.credential_service import create_credential_pdf


router = APIRouter(prefix="/admin/students")
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))
ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _guard(request: Request):
    return request.session.get("admin")


def _clean(value: str, max_length: int) -> str:
    return " ".join(value.strip().split())[:max_length]


async def _save_photo(photo: UploadFile | None) -> str | None:
    if not photo or not photo.filename:
        return None
    content = await photo.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"La fotografía excede {settings.MAX_UPLOAD_MB} MB")
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
        extension = ALLOWED_IMAGE_FORMATS.get(image.format or "")
        if not extension:
            raise ValueError("Usa una imagen JPG, PNG o WebP")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("El archivo no es una imagen válida") from exc
    filename = f"student-{secrets.token_hex(12)}{extension}"
    (settings.UPLOAD_DIR / filename).write_bytes(content)
    return filename


def _form_context(request: Request, db: Session, *, student=None, error=None):
    careers = db.scalars(select(Student.carrera).where(Student.eliminado.is_(False)).distinct().order_by(Student.carrera)).all()
    campuses = db.scalars(select(Student.plantel).where(Student.eliminado.is_(False)).distinct().order_by(Student.plantel)).all()
    return {"admin": _guard(request), "student": student, "error": error,
            "careers": careers, "campuses": campuses,
            "suggested_matricula": suggest_next_matricula(db),
            "default_expiry": date.today() + timedelta(days=settings.STUDENT_DEFAULT_VALIDITY_DAYS),
            "csrf_token": get_csrf_token(request), "active_page": "students"}


@router.get("", response_class=HTMLResponse)
def students_list(request: Request, q: str = "", carrera: str = "", plantel: str = "", estado: str = "",
                  alerta: str = "", papelera: str = "",
                  db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    in_trash = papelera == "1"
    query = select(Student).where(Student.eliminado.is_(in_trash))
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(Student.matricula.ilike(term), Student.nombres.ilike(term),
                                Student.apellido_paterno.ilike(term), Student.apellido_materno.ilike(term)))
    if carrera:
        query = query.where(Student.carrera == carrera)
    if plantel:
        query = query.where(Student.plantel == plantel)
    if estado in {"activo", "inactivo"}:
        query = query.where(Student.activo.is_(estado == "activo"))
    expiry_limit = date.today() + timedelta(days=30)
    if alerta == "por_vencer":
        query = query.where(Student.fecha_vencimiento >= date.today(), Student.fecha_vencimiento <= expiry_limit)
    elif alerta == "vencida":
        query = query.where(Student.fecha_vencimiento < date.today())
    elif alerta == "sin_foto":
        query = query.where(Student.foto.is_(None))
    students = db.scalars(query.order_by(Student.apellido_paterno, Student.nombres)).all()
    careers = db.scalars(select(Student.carrera).where(Student.eliminado.is_(False)).distinct().order_by(Student.carrera)).all()
    campuses = db.scalars(select(Student.plantel).where(Student.eliminado.is_(False)).distinct().order_by(Student.plantel)).all()
    return templates.TemplateResponse(request, "students.html", {
        "admin": _guard(request), "students": students, "careers": careers, "campuses": campuses,
        "filters": {"q": q, "carrera": carrera, "plantel": plantel, "estado": estado,
                    "alerta": alerta, "papelera": papelera}, "in_trash": in_trash,
        "student_stats": {
            "total": db.scalar(select(func.count(Student.id)).where(Student.eliminado.is_(False))) or 0,
            "active": db.scalar(select(func.count(Student.id)).where(Student.activo.is_(True), Student.eliminado.is_(False))) or 0,
            "expiring": db.scalar(select(func.count(Student.id)).where(Student.activo.is_(True), Student.eliminado.is_(False), Student.fecha_vencimiento >= date.today(), Student.fecha_vencimiento <= expiry_limit)) or 0,
            "no_photo": db.scalar(select(func.count(Student.id)).where(Student.foto.is_(None), Student.eliminado.is_(False))) or 0,
            "trash": db.scalar(select(func.count(Student.id)).where(Student.eliminado.is_(True))) or 0,
        },
        "csrf_token": get_csrf_token(request), "active_page": "students", "today": date.today(),
    })


@router.get("/new", response_class=HTMLResponse)
def student_new(request: Request, db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "student_form.html", _form_context(request, db))


@router.post("/new")
async def student_create(
    request: Request, matricula: str = Form(...), nombres: str = Form(...), apellido_paterno: str = Form(...),
    apellido_materno: str = Form(""), carrera: str = Form(...), grupo: str = Form("Sin grupo"),
    plantel: str = Form(...), turno: str = Form(...),
    fecha_vencimiento: date = Form(...), activo: bool = Form(False), csrf_token: str = Form(...),
    photo: UploadFile | None = File(None), db: Session = Depends(get_db),
):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    matricula = _clean(matricula, 32)
    if db.scalar(select(Student).where(Student.matricula == matricula)):
        return templates.TemplateResponse(request, "student_form.html", _form_context(request, db, error="La matrícula ya existe."), status_code=422)
    try:
        photo_name = await _save_photo(photo)
        student = Student(
            student_id=f"SAU-{secrets.token_hex(8)}", matricula=matricula, nombres=_clean(nombres, 120),
            apellido_paterno=_clean(apellido_paterno, 80), apellido_materno=_clean(apellido_materno, 80),
            carrera=_clean(carrera, 160), grupo=_clean(grupo, 60) or "Sin grupo",
            plantel=_clean(plantel, 120), turno=_clean(turno, 40),
            foto=photo_name, activo=activo, fecha_vencimiento=fecha_vencimiento,
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        generate_student_qr(student.id, db)
        return RedirectResponse(f"/admin/students/{student.id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(request, "student_form.html", _form_context(request, db, error=str(exc)), status_code=422)


@router.get("/import", response_class=HTMLResponse)
def student_import_page(request: Request):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "student_import.html", {
        "admin": _guard(request), "result": None, "error": None,
        "csrf_token": get_csrf_token(request), "active_page": "students",
    })


@router.post("/import", response_class=HTMLResponse)
async def student_import(request: Request, file: UploadFile = File(...), action: str = Form("preview"),
                         csrf_token: str = Form(...), db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    try:
        result = process_student_file(await file.read(), file.filename or "", db, commit=action == "import")
        error = None
    except ValueError as exc:
        result, error = None, str(exc)
    return templates.TemplateResponse(request, "student_import.html", {
        "admin": _guard(request), "result": result, "error": error,
        "csrf_token": get_csrf_token(request), "active_page": "students",
    }, status_code=422 if error else 200)


@router.get("/import/sample")
def student_import_sample(request: Request):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    return Response(sample_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=plantilla-alumnos.csv"})


@router.get("/{student_id}", response_class=HTMLResponse)
def student_detail(student_id: int, request: Request, db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    student = db.get(Student, student_id)
    if not student:
        return RedirectResponse("/admin/students", status_code=303)
    return templates.TemplateResponse(request, "student_detail.html", {
        **_form_context(request, db, student=student), "qr_exists": (settings.QR_DIR / f"{student.matricula}.png").exists()
    })


@router.get("/{student_id}/edit", response_class=HTMLResponse)
def student_edit(student_id: int, request: Request, db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    student = db.get(Student, student_id)
    if not student or student.eliminado:
        return RedirectResponse("/admin/students", status_code=303)
    return templates.TemplateResponse(request, "student_form.html", _form_context(request, db, student=student))


@router.post("/{student_id}/edit")
async def student_update(
    student_id: int, request: Request, matricula: str = Form(...), nombres: str = Form(...),
    apellido_paterno: str = Form(...), apellido_materno: str = Form(""), carrera: str = Form(...),
    grupo: str = Form("Sin grupo"), plantel: str = Form(...), turno: str = Form(...),
    fecha_vencimiento: date = Form(...),
    activo: bool = Form(False), csrf_token: str = Form(...), photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    student = db.get(Student, student_id)
    if not student or student.eliminado:
        return RedirectResponse("/admin/students", status_code=303)
    duplicate = db.scalar(select(Student).where(Student.matricula == _clean(matricula, 32), Student.id != student.id))
    if duplicate:
        return templates.TemplateResponse(request, "student_form.html", _form_context(request, db, student=student, error="La matrícula ya existe."), status_code=422)
    try:
        new_photo = await _save_photo(photo)
        old_qr = settings.QR_DIR / f"{student.matricula}.png"
        student.matricula = _clean(matricula, 32)
        student.nombres = _clean(nombres, 120)
        student.apellido_paterno = _clean(apellido_paterno, 80)
        student.apellido_materno = _clean(apellido_materno, 80)
        student.carrera = _clean(carrera, 160)
        student.grupo = _clean(grupo, 60) or "Sin grupo"
        student.plantel = _clean(plantel, 120)
        student.turno = _clean(turno, 40)
        student.fecha_vencimiento = fecha_vencimiento
        student.activo = activo
        if new_photo:
            student.foto = new_photo
        db.commit()
        if old_qr.name != f"{student.matricula}.png" and old_qr.exists():
            old_qr.unlink(missing_ok=True)
        generate_student_qr(student.id, db)
        return RedirectResponse(f"/admin/students/{student.id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(request, "student_form.html", _form_context(request, db, student=student, error=str(exc)), status_code=422)


@router.post("/{student_id}/toggle")
def student_toggle(student_id: int, request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    student = db.get(Student, student_id)
    if student and not student.eliminado:
        student.activo = not student.activo
        db.commit()
    return RedirectResponse(f"/admin/students/{student_id}", status_code=303)


@router.post("/{student_id}/delete")
def student_delete(student_id: int, request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _guard(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    student = db.get(Student, student_id)
    if student and not student.eliminado:
        student.eliminado = True
        student.activo = False
        student.deleted_at = local_now()
        student.deleted_by = admin["id"]
        record_audit(db, admin["id"], "BORRAR", "ALUMNO", student.id,
                     f"{student.matricula} · {student.nombre_completo}")
        db.commit()
    return RedirectResponse("/admin/students", status_code=303)


@router.post("/bulk")
def students_bulk(request: Request, action: str = Form(...), ids: list[int] = Form(default=[]),
                  csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _guard(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    restore = action == "restore"
    for student in db.scalars(select(Student).where(Student.id.in_(ids[:500]))).all():
        if restore and student.eliminado:
            student.eliminado, student.deleted_at, student.deleted_by = False, None, None
            record_audit(db, admin["id"], "RESTAURAR", "ALUMNO", student.id, student.matricula)
        elif action == "delete" and not student.eliminado:
            student.eliminado, student.activo = True, False
            student.deleted_at, student.deleted_by = local_now(), admin["id"]
            record_audit(db, admin["id"], "BORRAR", "ALUMNO", student.id, student.matricula)
    db.commit()
    return RedirectResponse(f"/admin/students{'?papelera=1' if restore else ''}", status_code=303)


@router.post("/{student_id}/restore")
def student_restore(student_id: int, request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    admin = _guard(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    student = db.get(Student, student_id)
    if student and student.eliminado:
        student.eliminado = False
        student.deleted_at = None
        student.deleted_by = None
        record_audit(db, admin["id"], "RESTAURAR", "ALUMNO", student.id, student.matricula)
        db.commit()
    return RedirectResponse("/admin/students?papelera=1", status_code=303)


@router.post("/{student_id}/qr")
def regenerate_qr(student_id: int, request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    validate_csrf(request, csrf_token)
    student = db.get(Student, student_id)
    if student and not student.eliminado:
        generate_student_qr(student_id, db, rotate=True)
    return RedirectResponse(f"/admin/students/{student_id}", status_code=303)


@router.get("/{student_id}/qr")
def download_qr(student_id: int, request: Request, db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    student = db.get(Student, student_id)
    if not student or student.eliminado:
        return RedirectResponse("/admin/students", status_code=303)
    path = settings.QR_DIR / f"{student.matricula}.png"
    if not path.exists():
        path = generate_student_qr(student.id, db)
    return FileResponse(path, media_type="image/png", filename=f"QR-{student.matricula}.png")


@router.get("/{student_id}/credential")
def download_credential(student_id: int, request: Request, db: Session = Depends(get_db)):
    if not _guard(request):
        return RedirectResponse("/admin/login", status_code=303)
    student = db.get(Student, student_id)
    if not student or student.eliminado:
        return RedirectResponse("/admin/students", status_code=303)
    qr_path = settings.QR_DIR / f"{student.matricula}.png"
    if not qr_path.exists():
        qr_path = generate_student_qr(student.id, db)
    return Response(create_credential_pdf(student, qr_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Credencial-{student.matricula}.pdf"'})
