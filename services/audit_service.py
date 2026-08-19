from sqlalchemy.orm import Session

from database.models import AuditLog


def record_audit(db: Session, admin_id: int | None, action: str, entity: str,
                 entity_id: int, detail: str = "") -> None:
    db.add(AuditLog(admin_id=admin_id, accion=action[:40], entidad=entity[:40],
                    entidad_id=entity_id, detalle=detail[:500]))
