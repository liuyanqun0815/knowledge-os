import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pg_enabled() -> bool:
    return os.getenv("AKOS_USE_PG", "false").lower() == "true"


pytestmark = pytest.mark.skipif(
    not _pg_enabled(),
    reason="requires AKOS_USE_PG=true",
)


def _run_sql_script(engine, script_path: Path) -> None:
    from sqlalchemy import text

    content = script_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in content.split(";") if s.strip() and not s.strip().startswith("--")]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


@pytest.fixture(scope="module")
def pg_engine():
    from infra.db import get_engine, reset_engine
    from infra.settings import Settings

    reset_engine()
    engine = get_engine(Settings(use_pg=True))
    _run_sql_script(engine, ROOT / "infra" / "schema.sql")
    _run_sql_script(engine, ROOT / "infra" / "migrations" / "002_knowledge_bases.sql")
    yield engine
    reset_engine()


@pytest.fixture
def pg_kb_repo(pg_engine):
    from knowledge_base.pg_repo import PgKnowledgeBaseRepo

    return PgKnowledgeBaseRepo(pg_engine)


def test_create_and_get_knowledge_base(pg_kb_repo):
    kb = pg_kb_repo.create(name="测试库", domain_type="ecommerce_cs", description="")
    loaded = pg_kb_repo.get(kb.id)
    assert loaded is not None
    assert loaded.name == "测试库"
    assert loaded.domain_type == "ecommerce_cs"
    assert loaded.status == "active"
    assert loaded.description == ""


def test_list_knowledge_bases(pg_kb_repo):
    kb = pg_kb_repo.create(name="列表库", domain_type="generic", description="desc")
    all_kbs = pg_kb_repo.list()
    assert any(item.id == kb.id for item in all_kbs)


def test_update_knowledge_base(pg_kb_repo):
    kb = pg_kb_repo.create(name="旧名", domain_type="ecommerce_cs", description="")
    updated = pg_kb_repo.update(kb.id, name="新名", description="新描述")
    assert updated is not None
    assert updated.name == "新名"
    assert updated.description == "新描述"
    loaded = pg_kb_repo.get(kb.id)
    assert loaded is not None
    assert loaded.name == "新名"


def test_archive_knowledge_base(pg_kb_repo):
    kb = pg_kb_repo.create(name="归档库", domain_type="ecommerce_cs", description="")
    archived = pg_kb_repo.archive(kb.id)
    assert archived is not None
    assert archived.status == "archived"
    active_only = pg_kb_repo.list(include_archived=False)
    assert not any(item.id == kb.id for item in active_only)
    all_kbs = pg_kb_repo.list(include_archived=True)
    assert any(item.id == kb.id for item in all_kbs)
