import os
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """测试会话启动前注入 LLM Key，避免 create_app 校验失败。"""
    os.environ.setdefault("AKOS_LLM_API_KEY", "pytest-llm-key")
    from infra.settings import get_settings

    get_settings.cache_clear()

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
    statements: list[str] = []
    buf: list[str] = []
    in_dollar = False
    for line in content.splitlines():
        stripped = line.strip()
        if not in_dollar and stripped.startswith("--"):
            continue
        if "$$" in line:
            # Toggle for each $$ pair on the line (handles DO $$ ... $$;).
            in_dollar = (line.count("$$") % 2 == 1) != in_dollar
        buf.append(line)
        if not in_dollar and stripped.endswith(";"):
            statement = "\n".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
    trailing = "\n".join(buf).strip()
    if trailing:
        statements.append(trailing)

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
    from akos.bootstrap import build_orchestrator_for_kb

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
    run_sql_script(engine, ROOT / "infra" / "migrations" / "008_source_chunks_stale_unique.sql")
    from infra.schema_bootstrap import _sources_pk_is_kb_scoped

    migration_009 = ROOT / "infra" / "migrations" / "009_sources_kb_scoped_pk.sql"
    if not _sources_pk_is_kb_scoped(engine):
        run_sql_script(engine, migration_009)
    run_sql_script(engine, ROOT / "infra" / "migrations" / "010_kb_graph_enabled.sql")
    yield engine
    reset_engine()


@pytest.fixture(scope="session")
def pg_kb_repo(pg_engine):
    from akos.adapters.persistence.kb_pg import PgKnowledgeBaseRepo

    return PgKnowledgeBaseRepo(pg_engine)
