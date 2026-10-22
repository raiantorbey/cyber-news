import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def load_initial_migration():
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("signalwatch_initial_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_seed_bulk_insert_uses_json_type_and_mapping_values(monkeypatch) -> None:
    migration = load_initial_migration()
    captured = {}

    def capture_bulk_insert(table, rows, **kwargs):
        captured["table"] = table
        captured["rows"] = rows
        captured["kwargs"] = kwargs

    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.op, "bulk_insert", capture_bulk_insert)
    migration._seed_default_sources()

    assert isinstance(captured["table"].c.config.type, sa.JSON)
    assert len(captured["rows"]) == 7
    assert all(isinstance(row["config"], dict) for row in captured["rows"])
    dialect = postgresql.dialect()
    bind_processor = captured["table"].c.config.type.dialect_impl(dialect).bind_processor(dialect)
    assert bind_processor is not None
    assert bind_processor(captured["rows"][0]["config"]) == "{}"
    assert captured["kwargs"] == {}
