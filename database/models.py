from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    matricula: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    nombres: Mapped[str] = mapped_column(String(120), index=True)
    apellido_paterno: Mapped[str] = mapped_column(String(80), index=True)
    apellido_materno: Mapped[str] = mapped_column(String(80), default="")
    carrera: Mapped[str] = mapped_column(String(160), index=True)
    grupo: Mapped[str] = mapped_column(String(60), default="Sin grupo", index=True)
    plantel: Mapped[str] = mapped_column(String(120), index=True)
    turno: Mapped[str] = mapped_column(String(40))
    foto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qr_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    eliminado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    access_records: Mapped[list["AccessRecord"]] = relationship(back_populates="student")

    @property
    def nombre_completo(self) -> str:
        return " ".join(filter(None, (self.nombres, self.apellido_paterno, self.apellido_materno)))


class AuthorizedPersonnel(Base):
    __tablename__ = "authorized_personnel"

    id: Mapped[int] = mapped_column(primary_key=True)
    personnel_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    numero_empleado: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    nombres: Mapped[str] = mapped_column(String(120), index=True)
    apellido_paterno: Mapped[str] = mapped_column(String(80), index=True)
    apellido_materno: Mapped[str] = mapped_column(String(80), default="")
    tipo_personal: Mapped[str] = mapped_column(String(40), default="DOCENTE", index=True)
    area: Mapped[str] = mapped_column(String(160), default="", index=True)
    plantel: Mapped[str] = mapped_column(String(120), index=True)
    turno: Mapped[str] = mapped_column(String(40))
    foto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qr_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, index=True)
    eliminado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    access_records: Mapped[list["AccessRecord"]] = relationship(back_populates="personnel")

    @property
    def nombre_completo(self) -> str:
        return " ".join(filter(None, (self.nombres, self.apellido_paterno, self.apellido_materno)))


class AccessRecord(Base):
    __tablename__ = "access_records"
    __table_args__ = (
        Index("ix_access_datetime_result", "datetime", "resultado"),
        Index("ix_access_student_datetime", "student_id", "datetime"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    personnel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("authorized_personnel.id"), nullable=True, index=True)
    tipo_movimiento: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    hora: Mapped[time] = mapped_column(Time)
    datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    resultado: Mapped[str] = mapped_column(String(16), index=True)
    motivo: Mapped[str] = mapped_column(String(255), default="")
    dispositivo: Mapped[str] = mapped_column(String(100))
    qr_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    eliminado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    student: Mapped[Optional[Student]] = relationship(back_populates="access_records")
    personnel: Mapped[Optional[AuthorizedPersonnel]] = relationship(back_populates="access_records")

    @property
    def person(self):
        return self.student or self.personnel

    @property
    def person_kind(self) -> str:
        return "ALUMNO" if self.student else (self.personnel.tipo_personal if self.personnel else "NO IDENTIFICADO")


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(120))
    rol: Mapped[str] = mapped_column(String(40), default="ADMIN")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    ubicacion: Mapped[str] = mapped_column(String(160))
    identificador: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class DailyOperation(Base):
    """Jornada operativa: archiva el resumen diario sin eliminar movimientos."""

    __tablename__ = "daily_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(16), default="ABIERTA", index=True)
    abierta_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cerrada_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    abierta_por: Mapped[Optional[int]] = mapped_column(ForeignKey("administrators.id"), nullable=True)
    cerrada_por: Mapped[Optional[int]] = mapped_column(ForeignKey("administrators.id"), nullable=True)
    nota_apertura: Mapped[str] = mapped_column(Text, default="Apertura automática")
    nota_cierre: Mapped[str] = mapped_column(Text, default="")
    entradas_cierre: Mapped[int] = mapped_column(Integer, default=0)
    salidas_cierre: Mapped[int] = mapped_column(Integer, default=0)
    rechazados_cierre: Mapped[int] = mapped_column(Integer, default=0)
    personas_dentro_cierre: Mapped[int] = mapped_column(Integer, default=0)
    eliminado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("administrators.id"), nullable=True, index=True)
    accion: Mapped[str] = mapped_column(String(40), index=True)
    entidad: Mapped[str] = mapped_column(String(40), index=True)
    entidad_id: Mapped[int] = mapped_column(Integer, index=True)
    detalle: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
