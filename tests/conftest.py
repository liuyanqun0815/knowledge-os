import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def pg_enabled() -> bool:
    return os.getenv("AKOS_USE_PG", "false").lower() == "true"


def run_sql_script(engine, script_path: Path) -> None:
    from sqlalchemy import text

    content = script_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in content.split(";") if s.strip() and not s.strip().startswith("--")]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


@pytest.fixture
def any_uuid() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def build_orchestrator_deps():
    from infra.bootstrap import build_orchestrator_deps as _build

    return _build


@pytest.fixture(scope="module")
def pg_engine():
    if not pg_enabled():
        pytest.skip("requires AKOS_USE_PG=true")

    from infra.db import get_engine, reset_engine
    from infra.settings import Settings

    reset_engine()
    engine = get_engine(Settings(use_pg=True))
    run_sql_script(engine, ROOT / "infra" / "schema.sql")
    run_sql_script(engine, ROOT / "infra" / "migrations" / "002_knowledge_bases.sql")
    yield engine
    reset_engine()


@pytest.fixture
def pg_kb_repo(pg_engine):
    from knowledge_base.pg_repo import PgKnowledgeBaseRepo

    return PgKnowledgeBaseRepo(pg_engine)
