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
    assert loaded.graph_enabled is False


def test_create_knowledge_base_with_graph_enabled(pg_kb_repo):
    kb = pg_kb_repo.create(
        name="有图库",
        domain_type="generic",
        description="",
        graph_enabled=True,
    )
    loaded = pg_kb_repo.get(kb.id)
    assert loaded is not None
    assert loaded.graph_enabled is True


def test_create_knowledge_base_with_graph_disabled(pg_kb_repo):
    kb = pg_kb_repo.create(
        name="无图库",
        domain_type="generic",
        description="",
        graph_enabled=False,
    )
    loaded = pg_kb_repo.get(kb.id)
    assert loaded is not None
    assert loaded.graph_enabled is False


def test_update_graph_enabled(pg_kb_repo):
    kb = pg_kb_repo.create(name="切换图", domain_type="generic", description="")
    updated = pg_kb_repo.update(kb.id, graph_enabled=False)
    assert updated is not None
    assert updated.graph_enabled is False
    reenabled = pg_kb_repo.update(kb.id, graph_enabled=True)
    assert reenabled is not None
    assert reenabled.graph_enabled is True


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
