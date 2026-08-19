"""Actualiza el esquema sin borrar alumnos, QR ni movimientos históricos."""

from database.database import SessionLocal, init_db
from database.migrations import apply_compatible_migrations
from services.day_service import ensure_today_operation


def migrate() -> None:
    init_db()
    changes = apply_compatible_migrations()
    with SessionLocal() as db:
        operation = ensure_today_operation(db)
        print(f"Esquema actualizado. Jornada {operation.fecha}: {operation.estado}")
        print("Los alumnos y registros existentes se conservaron.")
        print(f"Cambios aplicados: {len(changes)}")


if __name__ == "__main__":
    migrate()
