from __future__ import annotations

from sqlalchemy import inspect, text

from database.database import engine


SOFT_DELETE_TABLES = ("students", "access_records", "daily_operations")


def apply_compatible_migrations() -> list[str]:
    """Añade columnas compatibles a SQLite sin reconstruir ni borrar tablas."""
    changes: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in SOFT_DELETE_TABLES:
            if table not in existing_tables:
                continue
            columns = {column["name"] for column in inspect(engine).get_columns(table)}
            additions = {
                "eliminado": "BOOLEAN NOT NULL DEFAULT 0",
                "deleted_at": "DATETIME NULL",
                "deleted_by": "INTEGER NULL",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
                    changes.append(f"{table}.{name}")
        if "access_records" in existing_tables:
            access_columns = {column["name"] for column in inspect(engine).get_columns("access_records")}
            if "personnel_id" not in access_columns:
                connection.execute(text("ALTER TABLE access_records ADD COLUMN personnel_id INTEGER NULL"))
                changes.append("access_records.personnel_id")
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_access_records_personnel_id ON access_records (personnel_id)"))
        if "students" in existing_tables:
            student_columns = {column["name"] for column in inspect(engine).get_columns("students")}
            if "grupo" not in student_columns:
                connection.execute(text(
                    "ALTER TABLE students ADD COLUMN grupo VARCHAR(60) NOT NULL DEFAULT 'Sin grupo'"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_students_grupo ON students (grupo)"))
                changes.append("students.grupo")
    return changes
