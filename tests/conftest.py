import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

TEST_KB_NAME = "test-ecommerce"


def pg_enabled() -> bool:
    return os.getenv("AKOS_USE_PG", "false").lower() == "true"


def admin_upload_item(response) -> dict:
    body = response.json()
    if "results" in body:
        assert body["results"], "upload returned no results"
        return body["results"][0]
    return body


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


@pytest.fixture(scope="session")
def seeded_kb_id(request):
    if not pg_enabled():
        return "default"
    pg_kb_repo = request.getfixturevalue("pg_kb_repo")
    kb = pg_kb_repo.create(name=TEST_KB_NAME, domain_type="ecommerce_cs", description="ci")
    return kb.id


@pytest.fixture
def build_orchestrator_deps(seeded_kb_id):
    from infra.bootstrap import build_orchestrator_for_kb

    def _build():
        return build_orchestrator_for_kb(seeded_kb_id).deps

    return _build


@pytest.fixture(scope="session")
def pg_engine():
    if not pg_enabled():
        pytest.skip("requires AKOS_USE_PG=true")

    from infra.db import get_engine, reset_engine
    from infra.settings import Settings

    reset_engine()
    engine = get_engine(Settings(use_pg=True))
    run_sql_script(engine, ROOT / "infra" / "schema.sql")
    run_sql_script(engine, ROOT / "infra" / "migrations" / "002_knowledge_bases.sql")
    run_sql_script(engine, ROOT / "infra" / "migrations" / "003_evolution.sql")
    run_sql_script(engine, ROOT / "infra" / "migrations" / "004_procedures.sql")
    run_sql_script(engine, ROOT / "infra" / "migrations" / "005_source_chunks.sql")
    run_sql_script(engine, ROOT / "infra" / "migrations" / "006_topic_clusters.sql")
    yield engine
    reset_engine()


@pytest.fixture(scope="session")
def pg_kb_repo(pg_engine):
    from knowledge_base.pg_repo import PgKnowledgeBaseRepo

    return PgKnowledgeBaseRepo(pg_engine)
