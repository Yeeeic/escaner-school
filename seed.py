from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from sqlalchemy import select

from config import settings
from database.database import SessionLocal, init_db
from database.models import Administrator, Device, Student
from security import hash_password
from services.qr_service import generate_student_qr


STUDENTS = [
    ("20260001", "Andrea", "Ramírez", "Soto", "Ingeniería en Sistemas", "Campus Centro", "Matutino"),
    ("20260002", "Diego", "Hernández", "Luna", "Arquitectura", "Campus Centro", "Vespertino"),
    ("20260003", "Valeria", "Cruz", "Mendoza", "Administración", "Campus Norte", "Matutino"),
    ("20260004", "Emiliano", "Torres", "Ríos", "Ingeniería Industrial", "Campus Norte", "Mixto"),
    ("20260005", "Camila", "Flores", "Reyes", "Derecho", "Campus Centro", "Matutino"),
    ("20260006", "Santiago", "Morales", "Vega", "Diseño Digital", "Campus Sur", "Vespertino"),
    ("20260007", "Renata", "García", "Silva", "Psicología", "Campus Sur", "Matutino"),
    ("20260008", "Mateo", "Castillo", "Nava", "Contaduría", "Campus Centro", "Nocturno"),
    ("20260009", "Lucía", "Navarro", "Paz", "Medicina", "Campus Norte", "Mixto"),
    ("20260010", "Sebastián", "Ortega", "León", "Ingeniería Mecatrónica", "Campus Sur", "Vespertino"),
]


def seed() -> None:
    load_dotenv(settings.BASE_DIR / ".env", override=True)
    password = os.getenv("ADMIN_INITIAL_PASSWORD", "")
    if len(password) < 8:
        raise SystemExit("Configura ADMIN_INITIAL_PASSWORD (mínimo 8 caracteres) en .env antes de ejecutar seed.py")
    init_db()
    with SessionLocal() as db:
        admin = db.scalar(select(Administrator).where(Administrator.username == "admin"))
        if not admin:
            db.add(Administrator(username="admin", password_hash=hash_password(password),
                                 nombre="Administrador del sistema", rol="SUPERADMIN", activo=True))
        device = db.scalar(select(Device).where(Device.identificador == settings.DEVICE_IDENTIFIER))
        if not device:
            db.add(Device(nombre="Kiosco principal", ubicacion="Entrada principal",
                          identificador=settings.DEVICE_IDENTIFIER, activo=True))
        db.commit()

        created = []
        for index, row in enumerate(STUDENTS, 1):
            if db.scalar(select(Student).where(Student.matricula == row[0])):
                continue
            student = Student(
                student_id=f"SAU-DEMO-{index:04d}", matricula=row[0], nombres=row[1],
                apellido_paterno=row[2], apellido_materno=row[3], carrera=row[4],
                grupo=f"{((index - 1) % 4) + 1}{'A' if index % 2 else 'B'}",
                plantel=row[5], turno=row[6], activo=True,
                fecha_vencimiento=date.today() + timedelta(days=365),
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            generate_student_qr(student.id, db)
            created.append(student.matricula)
        print(f"Base inicializada. Alumnos nuevos: {len(created)}. Administrador: admin")
        print(f"QR disponibles en: {settings.QR_DIR}")


if __name__ == "__main__":
    seed()
