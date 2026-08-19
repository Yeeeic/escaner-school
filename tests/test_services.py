from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config import settings
from database.database import Base
from database.models import AccessRecord, AuthorizedPersonnel, Student
from services.access_service import grouped_people_inside, process_access
from services.day_service import close_operation, ensure_today_operation, stats_for_date
from services.qr_service import (build_personnel_qr_data, build_qr_data, generate_personnel_qr,
                                 generate_student_qr, validate_qr)
from services.student_import_service import process_student_file


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "QR_DIR", tmp_path)
    with Session(engine) as session:
        yield session


def make_student(db: Session, **overrides) -> Student:
    values = {
        "student_id": "SAU-TEST-001", "matricula": "TEST001", "nombres": "Ada",
        "apellido_paterno": "Lovelace", "apellido_materno": "", "carrera": "Computación",
        "plantel": "Campus Pruebas", "turno": "Matutino", "activo": True,
        "fecha_vencimiento": date.today() + timedelta(days=30),
    }
    values.update(overrides)
    student = Student(**values)
    db.add(student); db.commit(); db.refresh(student)
    generate_student_qr(student.id, db)
    return student


def test_qr_signature_and_tampering(db):
    student = make_student(db)
    qr_data = build_qr_data(student)
    assert validate_qr(qr_data, db)["valid"] is True
    assert validate_qr(qr_data[:-1] + ("0" if qr_data[-1] != "0" else "1"), db)["reason"] == "QR ALTERADO"


def test_process_access_and_cooldown(db):
    student = make_student(db)
    qr_data = build_qr_data(student)
    first = process_access(qr_data, db)
    second = process_access(qr_data, db)
    assert first["authorized"] is True and first["movement"] == "ENTRADA"
    assert second["duplicate"] is True and second["movement"] == "ENTRADA"
    assert db.query(AccessRecord).count() == 1


def test_expired_credential_is_denied(db):
    student = make_student(db, student_id="SAU-TEST-EXPIRED", matricula="EXPIRED", fecha_vencimiento=date.today() - timedelta(days=1))
    result = process_access(build_qr_data(student), db)
    assert result["authorized"] is False
    assert result["reason"] == "CREDENCIAL VENCIDA"
    assert db.query(AccessRecord).one().resultado == "DENEGADO"


def test_closed_day_blocks_access_without_erasing_history(db):
    student = make_student(db, student_id="SAU-DAY-001", matricula="DAY001")
    operation = ensure_today_operation(db)
    close_operation(db, operation, admin_id=1, note="Cierre de prueba")
    result = process_access(build_qr_data(student), db)
    assert result["authorized"] is False
    assert result["reason"] == "JORNADA CERRADA"
    assert db.query(AccessRecord).count() == 0


def test_bulk_student_validation_and_import(db):
    content = ("matricula,nombres,apellido_paterno,apellido_materno,carrera,plantel,turno,fecha_vencimiento,activo\n"
               "20269999,Elena,Prueba,,Ingeniería,Campus Centro,Matutino,2099-12-31,SI\n").encode()
    preview = process_student_file(content, "alumnos.csv", db, commit=False)
    assert preview["valid"] == 1 and preview["created"] == 0
    imported = process_student_file(content, "alumnos.csv", db, commit=True)
    assert imported["created"] == 1
    assert db.query(Student).filter_by(matricula="20269999").one().qr_token


def test_deleted_student_qr_is_blocked(db):
    student = make_student(db, student_id="SAU-DELETED-001", matricula="DELETED001")
    qr_data = build_qr_data(student)
    student.eliminado = True
    student.activo = False
    db.commit()
    result = validate_qr(qr_data, db)
    assert result["valid"] is False
    assert result["reason"] == "CREDENCIAL ELIMINADA"


def test_deleted_record_no_longer_counts_in_day(db):
    student = make_student(db, student_id="SAU-RECORD-001", matricula="RECORD001")
    result = process_access(build_qr_data(student), db)
    assert result["authorized"] is True
    record = db.query(AccessRecord).one()
    assert stats_for_date(db, record.fecha)["entries"] == 1
    record.eliminado = True
    db.commit()
    assert stats_for_date(db, record.fecha)["entries"] == 0


def test_personnel_qr_access_and_inside_group(db):
    person = AuthorizedPersonnel(
        personnel_id="SAU-PER-TEST-001", numero_empleado="DOC001", nombres="Edsger",
        apellido_paterno="Dijkstra", apellido_materno="", tipo_personal="DOCENTE",
        area="Ingeniería", plantel="Campus Pruebas", turno="Matutino", activo=True,
        fecha_vencimiento=date.today() + timedelta(days=30),
    )
    db.add(person); db.commit(); db.refresh(person)
    generate_personnel_qr(person.id, db)
    result = process_access(build_personnel_qr_data(person), db)
    assert result["authorized"] is True
    assert result["student"]["kind"] == "personnel"
    assert db.query(AccessRecord).one().personnel_id == person.id
    groups = grouped_people_inside(db)
    assert groups["personnel_count"] == 1
    assert groups["personnel"]["DOCENTE"][0]["student"]["matricula"] == "DOC001"
