from app.db.migration_state import expected_schema_revision


def test_expected_schema_revision_is_current_alembic_head():
    assert expected_schema_revision() == "20260731_0017"
