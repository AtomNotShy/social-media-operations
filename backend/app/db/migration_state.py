from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


@lru_cache
def expected_schema_revision() -> str:
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent / "migrations"),
    )
    revision = ScriptDirectory.from_config(config).get_current_head()
    if revision is None:
        raise RuntimeError("Alembic migration head could not be resolved")
    return revision
