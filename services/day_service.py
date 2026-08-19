from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database.models import AccessRecord, DailyOperation, Student


def ensure_today_operation(db: Session, admin_id: int | None = None) -> DailyOperation:
    from services.access_service import local_now

    today = local_now().date()
    operation = db.scalar(select(DailyOperation).where(
        DailyOperation.fecha == today, DailyOperation.eliminado.is_(False)))
    if operation:
        return operation
    previous_open = db.scalars(select(DailyOperation).where(
        DailyOperation.fecha < today, DailyOperation.estado == "ABIERTA",
        DailyOperation.eliminado.is_(False))).all()
    for previous in previous_open:
        stats = stats_for_date(db, previous.fecha)
        previous.estado = "CERRADA"
        previous.cerrada_at = local_now()
        previous.nota_cierre = "Cierre automático por cambio de día"
        previous.entradas_cierre = stats["entries"]
        previous.salidas_cierre = stats["exits"]
        previous.rechazados_cierre = stats["denied"]
        previous.personas_dentro_cierre = stats["inside"]
    if previous_open:
        db.commit()
    operation = DailyOperation(fecha=today, estado="ABIERTA", abierta_at=local_now(), abierta_por=admin_id,
                               nota_apertura="Apertura automática por cambio de día")
    db.add(operation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        operation = db.scalar(select(DailyOperation).where(
            DailyOperation.fecha == today, DailyOperation.eliminado.is_(False)))
    return operation


def stats_for_date(db: Session, target_date) -> dict:
    from services.access_service import get_people_inside, local_now

    grouped = dict(db.execute(
        select(AccessRecord.tipo_movimiento, func.count(AccessRecord.id))
        .where(AccessRecord.fecha == target_date, AccessRecord.resultado == "AUTORIZADO",
               AccessRecord.eliminado.is_(False))
        .group_by(AccessRecord.tipo_movimiento)
    ).all())
    denied = db.scalar(select(func.count(AccessRecord.id)).where(
        AccessRecord.fecha == target_date, AccessRecord.resultado == "DENEGADO",
        AccessRecord.eliminado.is_(False))) or 0
    inside = len(get_people_inside(db, target_date))
    return {"entries": grouped.get("ENTRADA", 0), "exits": grouped.get("SALIDA", 0),
            "denied": denied, "inside": inside}


def close_operation(db: Session, operation: DailyOperation, admin_id: int, note: str = "") -> DailyOperation:
    from services.access_service import local_now

    if operation.estado == "CERRADA":
        return operation
    stats = stats_for_date(db, operation.fecha)
    operation.estado = "CERRADA"
    operation.cerrada_at = local_now()
    operation.cerrada_por = admin_id
    operation.nota_cierre = " ".join(note.strip().split())[:500]
    operation.entradas_cierre = stats["entries"]
    operation.salidas_cierre = stats["exits"]
    operation.rechazados_cierre = stats["denied"]
    operation.personas_dentro_cierre = stats["inside"]
    db.commit()
    db.refresh(operation)
    return operation


def reopen_operation(db: Session, operation: DailyOperation, admin_id: int, note: str = "") -> DailyOperation:
    from services.access_service import local_now

    operation.estado = "ABIERTA"
    operation.abierta_at = local_now()
    operation.abierta_por = admin_id
    operation.cerrada_at = None
    operation.cerrada_por = None
    operation.nota_cierre = ""
    operation.entradas_cierre = 0
    operation.salidas_cierre = 0
    operation.rechazados_cierre = 0
    operation.personas_dentro_cierre = 0
    operation.nota_apertura = "Reapertura: " + (" ".join(note.strip().split())[:450] or "sin nota")
    db.commit()
    db.refresh(operation)
    return operation


def operation_summary(db: Session, operation: DailyOperation) -> dict:
    stats = stats_for_date(db, operation.fecha)
    return {"id": operation.id, "date": operation.fecha.isoformat(),
            "date_label": operation.fecha.strftime("%d/%m/%Y"), "status": operation.estado,
            "opened_at": operation.abierta_at.strftime("%H:%M:%S") if operation.abierta_at else None,
            "closed_at": operation.cerrada_at.strftime("%H:%M:%S") if operation.cerrada_at else None,
            "opening_note": operation.nota_apertura, "closing_note": operation.nota_cierre,
            "deleted": operation.eliminado, "deleted_at": operation.deleted_at, **stats}


def operational_alerts(db: Session) -> dict:
    from services.access_service import get_people_inside, local_now

    now = local_now()
    expiry_limit = now.date() + timedelta(days=30)
    expiring = db.scalar(select(func.count(Student.id)).where(
        Student.activo.is_(True), Student.eliminado.is_(False), Student.fecha_vencimiento >= now.date(),
        Student.fecha_vencimiento <= expiry_limit)) or 0
    expired = db.scalar(select(func.count(Student.id)).where(
        Student.activo.is_(True), Student.eliminado.is_(False), Student.fecha_vencimiento < now.date())) or 0
    no_photo = db.scalar(select(func.count(Student.id)).where(
        Student.activo.is_(True), Student.eliminado.is_(False), Student.foto.is_(None))) or 0
    inside_rows = get_people_inside(db, now.date())
    long_stay = sum(1 for row in inside_rows if row["duration_minutes"] >= settings.LONG_STAY_HOURS * 60)
    repeated_denials = db.scalar(select(func.count()).select_from(
        select(AccessRecord.student_id).where(
            AccessRecord.fecha == now.date(), AccessRecord.resultado == "DENEGADO",
            AccessRecord.student_id.is_not(None), AccessRecord.eliminado.is_(False)).group_by(AccessRecord.student_id)
        .having(func.count(AccessRecord.id) >= 3).subquery())) or 0
    occupancy = len(inside_rows)
    return {"expiring": expiring, "expired": expired, "no_photo": no_photo,
            "long_stay": long_stay, "repeated_denials": repeated_denials,
            "capacity_limit": settings.CAPACITY_LIMIT,
            "occupancy_percent": min(100, round(occupancy * 100 / max(settings.CAPACITY_LIMIT, 1)))}
