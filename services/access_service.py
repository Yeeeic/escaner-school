from __future__ import annotations

import hashlib
import threading
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from config import settings
from database.models import AccessRecord, AuthorizedPersonnel, Student
from services.qr_service import validate_qr


_rejection_cache: dict[str, datetime] = {}
_cache_lock = threading.Lock()


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.TIMEZONE)).replace(tzinfo=None)


def _identity_dict(identity: Student | AuthorizedPersonnel) -> dict:
    if isinstance(identity, Student):
        return {
            "id": identity.id, "student_id": identity.student_id, "kind": "student",
            "type_label": "ESTUDIANTE", "name": identity.nombre_completo,
            "matricula": identity.matricula, "career": identity.carrera,
            "group": identity.grupo or identity.carrera, "campus": identity.plantel, "shift": identity.turno,
            "photo": f"/static/uploads/{identity.foto}" if identity.foto else "/static/images/default-avatar.svg",
            "active": identity.activo, "expires": identity.fecha_vencimiento.isoformat(),
        }
    return {
        "id": identity.id, "student_id": identity.personnel_id, "kind": "personnel",
        "type_label": identity.tipo_personal, "name": identity.nombre_completo,
        "matricula": identity.numero_empleado, "career": identity.area or identity.tipo_personal,
        "group": identity.tipo_personal, "campus": identity.plantel, "shift": identity.turno,
        "photo": f"/static/uploads/{identity.foto}" if identity.foto else "/static/images/default-avatar.svg",
        "active": identity.activo, "expires": identity.fecha_vencimiento.isoformat(),
    }


def _response(record: AccessRecord | None, *, authorized: bool, reason: str,
              identity: Student | AuthorizedPersonnel | None = None,
              duplicate: bool = False, movement: str | None = None) -> dict:
    now = record.datetime if record else local_now()
    return {
        "authorized": authorized, "duplicate": duplicate,
        "movement": movement or (record.tipo_movimiento if record else None),
        "result": "AUTORIZADO" if authorized else "DENEGADO", "reason": reason,
        # Se conserva el nombre `student` para compatibilidad con el kiosco existente.
        "student": _identity_dict(identity) if identity else None,
        "date": now.strftime("%d/%m/%Y"), "time": now.strftime("%H:%M:%S"),
        "timestamp": now.isoformat(),
    }


def _save_denied(db: Session, reason: str, qr_data: str,
                 identity: Student | AuthorizedPersonnel | None = None) -> AccessRecord:
    now = local_now()
    record = AccessRecord(
        student_id=identity.id if isinstance(identity, Student) else None,
        personnel_id=identity.id if isinstance(identity, AuthorizedPersonnel) else None,
        tipo_movimiento=None, fecha=now.date(), hora=now.time(), datetime=now,
        resultado="DENEGADO", motivo=reason, dispositivo=settings.DEVICE_IDENTIFIER,
        qr_reference=hashlib.sha256(qr_data.encode("utf-8", errors="ignore")).hexdigest()[:24],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _recent_rejection(qr_data: str) -> bool:
    key = hashlib.sha256(qr_data.encode("utf-8", errors="ignore")).hexdigest()
    now = local_now()
    with _cache_lock:
        expired = [item for item, timestamp in _rejection_cache.items() if now - timestamp > timedelta(minutes=2)]
        for item in expired:
            _rejection_cache.pop(item, None)
        previous = _rejection_cache.get(key)
        _rejection_cache[key] = now
    return bool(previous and (now - previous).total_seconds() < settings.ACCESS_COOLDOWN_SECONDS)


def process_access(qr_data: str, db: Session) -> dict:
    from services.day_service import ensure_today_operation

    operation = ensure_today_operation(db)
    if operation.estado == "CERRADA":
        return _response(None, authorized=False, reason="JORNADA CERRADA")
    validation = validate_qr(qr_data, db)
    if not validation["valid"]:
        reason = validation["reason"]
        if _recent_rejection(qr_data):
            return _response(None, authorized=False, reason=f"{reason} · lectura duplicada", duplicate=True)
        return _response(_save_denied(db, reason, qr_data), authorized=False, reason=reason)

    identity: Student | AuthorizedPersonnel = validation["identity"]
    if not identity.activo:
        if _recent_rejection(qr_data):
            return _response(None, authorized=False, reason="CREDENCIAL DESACTIVADA · lectura duplicada",
                             identity=identity, duplicate=True)
        record = _save_denied(db, "CREDENCIAL DESACTIVADA", qr_data, identity)
        return _response(record, authorized=False, reason="CREDENCIAL DESACTIVADA", identity=identity)
    if identity.fecha_vencimiento < local_now().date():
        if _recent_rejection(qr_data):
            return _response(None, authorized=False, reason="CREDENCIAL VENCIDA · lectura duplicada",
                             identity=identity, duplicate=True)
        record = _save_denied(db, "CREDENCIAL VENCIDA", qr_data, identity)
        return _response(record, authorized=False, reason="CREDENCIAL VENCIDA", identity=identity)

    now = local_now()
    identity_filter = (AccessRecord.student_id == identity.id if isinstance(identity, Student)
                       else AccessRecord.personnel_id == identity.id)
    last = db.scalar(select(AccessRecord).where(
        identity_filter, AccessRecord.resultado == "AUTORIZADO", AccessRecord.fecha == now.date(),
        AccessRecord.eliminado.is_(False)).order_by(AccessRecord.datetime.desc()).limit(1))
    movement = "SALIDA" if last and last.tipo_movimiento == "ENTRADA" else "ENTRADA"
    if last and (now - last.datetime).total_seconds() < settings.ACCESS_COOLDOWN_SECONDS:
        return _response(last, authorized=True, reason="LECTURA DUPLICADA IGNORADA", identity=identity,
                         duplicate=True, movement=last.tipo_movimiento)
    record = AccessRecord(
        student_id=identity.id if isinstance(identity, Student) else None,
        personnel_id=identity.id if isinstance(identity, AuthorizedPersonnel) else None,
        tipo_movimiento=movement, fecha=now.date(), hora=now.time(), datetime=now,
        resultado="AUTORIZADO", motivo="ACCESO AUTORIZADO", dispositivo=settings.DEVICE_IDENTIFIER,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _response(record, authorized=True, reason="ACCESO AUTORIZADO", identity=identity)


def _inside_for(db: Session, target_date: date, *, personnel: bool) -> list[dict]:
    identity_column = AccessRecord.personnel_id if personnel else AccessRecord.student_id
    latest = (select(identity_column.label("identity_id"), func.max(AccessRecord.datetime).label("latest_at"))
              .where(AccessRecord.resultado == "AUTORIZADO", identity_column.is_not(None),
                     AccessRecord.fecha == target_date, AccessRecord.eliminado.is_(False))
              .group_by(identity_column).subquery())
    rows = db.execute(select(AccessRecord).join(
        latest, (identity_column == latest.c.identity_id) & (AccessRecord.datetime == latest.c.latest_at)
    ).options(joinedload(AccessRecord.student), joinedload(AccessRecord.personnel)).where(
        AccessRecord.tipo_movimiento == "ENTRADA", AccessRecord.eliminado.is_(False)
    ).order_by(AccessRecord.datetime.desc())).scalars().unique().all()
    now = local_now()
    result = []
    for row in rows:
        identity = row.personnel if personnel else row.student
        if not identity or identity.eliminado:
            continue
        result.append({
            "student": _identity_dict(identity), "kind": "personnel" if personnel else "student",
            "group": identity.tipo_personal if personnel else (identity.grupo or identity.carrera),
            "entered_at": row.datetime.strftime("%H:%M:%S"), "entered_iso": row.datetime.isoformat(),
            "duration_minutes": max(0, int((now - row.datetime).total_seconds() // 60)),
        })
    return result


def get_people_inside(db: Session, target_date: date | None = None) -> list[dict]:
    target_date = target_date or local_now().date()
    return _inside_for(db, target_date, personnel=False) + _inside_for(db, target_date, personnel=True)


def grouped_people_inside(db: Session, target_date: date | None = None) -> dict:
    people = get_people_inside(db, target_date)
    student_groups: dict[str, list] = {}
    personnel_groups: dict[str, list] = {}
    for row in people:
        target = personnel_groups if row["kind"] == "personnel" else student_groups
        target.setdefault(row["group"] or "Sin grupo", []).append(row)
    return {"all": people, "students": student_groups, "personnel": personnel_groups,
            "student_count": sum(len(items) for items in student_groups.values()),
            "personnel_count": sum(len(items) for items in personnel_groups.values())}


def today_stats(db: Session) -> dict:
    from services.day_service import ensure_today_operation
    today = local_now().date()
    operation = ensure_today_operation(db)
    grouped = dict(db.execute(select(AccessRecord.tipo_movimiento, func.count(AccessRecord.id)).where(
        AccessRecord.fecha == today, AccessRecord.resultado == "AUTORIZADO",
        AccessRecord.eliminado.is_(False)).group_by(AccessRecord.tipo_movimiento)).all())
    denied = db.scalar(select(func.count(AccessRecord.id)).where(
        AccessRecord.fecha == today, AccessRecord.resultado == "DENEGADO",
        AccessRecord.eliminado.is_(False))) or 0
    return {"date": today.isoformat(), "entries": grouped.get("ENTRADA", 0),
            "exits": grouped.get("SALIDA", 0), "denied": denied,
            "inside": len(get_people_inside(db, today)), "day_status": operation.estado,
            "day_id": operation.id}


def recent_access(db: Session, limit: int = 8) -> list[dict]:
    records = db.execute(select(AccessRecord).options(
        joinedload(AccessRecord.student), joinedload(AccessRecord.personnel)
    ).where(AccessRecord.eliminado.is_(False)).order_by(
        AccessRecord.datetime.desc()).limit(min(max(limit, 1), 50))).scalars().unique().all()
    return [{"id": record.id, "student": record.person.nombre_completo if record.person else "No identificado",
             "matricula": (record.student.matricula if record.student else
                            record.personnel.numero_empleado if record.personnel else "—"),
             "movement": record.tipo_movimiento, "result": record.resultado, "reason": record.motivo,
             "time": record.datetime.strftime("%H:%M:%S"), "date": record.datetime.strftime("%d/%m/%Y")}
            for record in records]
