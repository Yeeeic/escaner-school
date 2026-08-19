from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

import qrcode
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database.models import AuthorizedPersonnel, Student


def _signature(student_id: str, nonce: str) -> str:
    message = f"{student_id}|{nonce}".encode("utf-8")
    return hmac.new(settings.QR_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_qr_data(student: Student) -> str:
    if not student.qr_token:
        raise ValueError("El alumno aún no tiene token QR")
    signed_token = f"{student.qr_token}.{_signature(student.student_id, student.qr_token)}"
    return f"{student.student_id}|{signed_token}"


def build_personnel_qr_data(person: AuthorizedPersonnel) -> str:
    if not person.qr_token:
        raise ValueError("La persona aún no tiene token QR")
    signed_token = f"{person.qr_token}.{_signature(person.personnel_id, person.qr_token)}"
    return f"{person.personnel_id}|{signed_token}"


def generate_student_qr(student_id: int | str, db: Session, rotate: bool = False) -> Path:
    if isinstance(student_id, int):
        student = db.get(Student, student_id)
    else:
        student = db.scalar(select(Student).where(Student.student_id == str(student_id)))
    if not student:
        raise ValueError("Alumno no encontrado")

    if rotate or not student.qr_token:
        student.qr_token = secrets.token_urlsafe(24)
        db.add(student)
        db.commit()
        db.refresh(student)

    data = build_qr_data(student)
    target = settings.QR_DIR / f"{student.matricula}.png"
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#102f2a", back_color="white")
    image.save(target)
    return target


def generate_personnel_qr(personnel_id: int | str, db: Session, rotate: bool = False) -> Path:
    if isinstance(personnel_id, int):
        person = db.get(AuthorizedPersonnel, personnel_id)
    else:
        person = db.scalar(select(AuthorizedPersonnel).where(
            AuthorizedPersonnel.personnel_id == str(personnel_id)))
    if not person:
        raise ValueError("Personal no encontrado")
    if rotate or not person.qr_token:
        person.qr_token = secrets.token_urlsafe(24)
        db.add(person)
        db.commit()
        db.refresh(person)
    data = build_personnel_qr_data(person)
    target = settings.QR_DIR / f"personal-{person.numero_empleado}.png"
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    qr.make_image(fill_color="#102f2a", back_color="white").save(target)
    return target


def validate_qr(qr_data: str, db: Session) -> dict:
    try:
        if not qr_data or len(qr_data) > 512:
            return {"valid": False, "reason": "QR INVÁLIDO"}
        student_id, signed_token = qr_data.strip().split("|", 1)
        nonce, received_signature = signed_token.rsplit(".", 1)
        if not student_id or not nonce or len(received_signature) != 64:
            return {"valid": False, "reason": "QR INVÁLIDO"}
    except ValueError:
        return {"valid": False, "reason": "QR INVÁLIDO"}

    student = db.scalar(select(Student).where(Student.student_id == student_id))
    person = student or db.scalar(select(AuthorizedPersonnel).where(
        AuthorizedPersonnel.personnel_id == student_id))
    if not person:
        reason = "PERSONAL NO REGISTRADO" if student_id.startswith("SAU-PER-") else "ALUMNO NO REGISTRADO"
        return {"valid": False, "reason": reason, "student_id": student_id}
    if person.eliminado:
        return {"valid": False, "reason": "CREDENCIAL ELIMINADA", "student_id": student_id}
    if not person.qr_token or not hmac.compare_digest(person.qr_token, nonce):
        return {"valid": False, "reason": "QR ALTERADO", "student_id": student_id}

    expected = _signature(student_id, nonce)
    if not hmac.compare_digest(expected, received_signature):
        return {"valid": False, "reason": "QR ALTERADO", "student_id": student_id}
    return {"valid": True, "student_id": student_id, "student": student,
            "personnel": None if student else person, "identity": person}
