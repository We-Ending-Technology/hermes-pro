from pathlib import Path


MIGRATION = Path(__file__).parents[2] / "supabase" / "migrations" / "20260917_autonomy_memory_watchdog.sql"


def test_autonomy_migration_declares_required_tables_and_rls():
    sql = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "hermes_memories",
        "hermes_incidents",
        "hermes_watchdog_checks",
        "hermes_reflections",
        "hermes_autonomy_policies",
    ):
        assert f"create table {table}" in sql.lower()
        assert f"alter table {table} enable row level security" in sql.lower()


def test_autonomy_migration_declares_incident_fingerprint_and_memory_status():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "fingerprint text not null unique" in sql
    assert "status text not null" in sql
    assert "confidence numeric" in sql
