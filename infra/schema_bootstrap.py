from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from infra.settings import Settings

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_schema_ready: set[str] = set()


def run_sql_script(engine: Engine, script_path: Path) -> None:
    raw = script_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if not line.strip().startswith("--")]
    content = "\n".join(lines)
    statements = [statement.strip() for statement in content.split(";") if statement.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def ensure_pg_schema(settings: Settings | None = None) -> None:
    """Apply schema.sql once per process (CREATE IF NOT EXISTS is idempotent)."""
    cfg = settings or Settings()
    if not cfg.use_pg:
        return

    cache_key = cfg.database_url
    if cache_key in _schema_ready:
        return

    from infra.db import get_engine

    run_sql_script(get_engine(cfg), _SCHEMA_PATH)
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    for name in (
        "005_source_chunks.sql",
        "006_topic_clusters.sql",
        "007_embeddings_1024.sql",
        "008_source_chunks_stale_unique.sql",
    ):
        migration_path = migrations_dir / name
        if migration_path.exists():
            run_sql_script(get_engine(cfg), migration_path)
    _schema_ready.add(cache_key)
