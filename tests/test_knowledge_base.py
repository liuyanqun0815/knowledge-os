import pytest

from tests.conftest import pg_enabled

pytestmark = pytest.mark.skipif(
    not pg_enabled(),
    reason="requires AKOS_USE_PG=true",
)


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
