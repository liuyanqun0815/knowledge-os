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


def _sources_pk_is_kb_scoped(engine: Engine) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint
                    WHERE conrelid = 'sources'::regclass
                      AND contype = 'p'
                      AND pg_get_constraintdef(oid) LIKE '%knowledge_base_id%'
                    """
                )
            ).scalar()
        )


def ensure_pg_schema(settings: Settings | None = None) -> None:
    """Apply schema.sql once per process (CREATE IF NOT EXISTS is idempotent)."""
    cfg = settings or Settings()
    if not cfg.use_pg:
        return

    cache_key = cfg.database_url
    if cache_key in _schema_ready:
        return

    from infra.db import get_engine

    engine = get_engine(cfg)
    run_sql_script(engine, _SCHEMA_PATH)
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    for name in (
        "005_source_chunks.sql",
        "006_topic_clusters.sql",
        "007_embeddings_1024.sql",
        "008_source_chunks_stale_unique.sql",
        "009_sources_kb_scoped_pk.sql",
        "010_kb_graph_enabled.sql",
    ):
        migration_path = migrations_dir / name
        if migration_path.exists():
            if name == "009_sources_kb_scoped_pk.sql" and _sources_pk_is_kb_scoped(engine):
                continue
            run_sql_script(engine, migration_path)
    _schema_ready.add(cache_key)
