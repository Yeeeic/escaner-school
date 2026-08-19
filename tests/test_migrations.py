from sqlalchemy import create_engine, inspect, text

from database import migrations


def test_soft_delete_migration_preserves_old_tables(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE students (id INTEGER PRIMARY KEY, matricula VARCHAR(32))"))
        connection.execute(text("CREATE TABLE access_records (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE daily_operations (id INTEGER PRIMARY KEY, fecha DATE)"))
        connection.execute(text("INSERT INTO students (id, matricula) VALUES (1, 'CONSERVAR')"))
    monkeypatch.setattr(migrations, "engine", engine)
    changes = migrations.apply_compatible_migrations()
    assert len(changes) == 11
    assert {"eliminado", "deleted_at", "deleted_by"}.issubset(
        {column["name"] for column in inspect(engine).get_columns("students")})
    assert "personnel_id" in {column["name"] for column in inspect(engine).get_columns("access_records")}
    assert "grupo" in {column["name"] for column in inspect(engine).get_columns("students")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT matricula FROM students WHERE id=1")).scalar_one() == "CONSERVAR"
    assert migrations.apply_compatible_migrations() == []
