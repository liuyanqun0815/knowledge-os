from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from compiler.service import _entity_id
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    return TestClient(create_app(data_root=str(tmp_path)))


def _cached_orchestrator(client: TestClient, kb_id: str):
    cache = client.app.state.orchestrator_cache
    if kb_id not in cache:
        cache[kb_id] = build_orchestrator_for_kb(kb_id)
    return cache[kb_id]


def _seed_graph(client: TestClient, kb_id: str = DEFAULT_IN_MEMORY_KB_ID) -> tuple[str, str]:
    orch = _cached_orchestrator(client, kb_id)
    graph = orch.deps.graph
    rule_id = _entity_id("七天无理由", "RefundRule")
    seller_id = _entity_id("卖家", "Concept")
    graph.upsert_entity(rule_id, "RefundRule", {"name": "七天无理由"})
    graph.upsert_entity(seller_id, "Concept", {"name": "卖家"})
    graph.upsert_relation(rule_id, "运费承担方", seller_id, {})
    return rule_id, seller_id


def test_graph_snapshot_returns_entities_and_edges(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    rule_id, seller_id = _seed_graph(admin_client, kb_id)

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/graph/snapshot")
    assert response.status_code == 200, response.text
    body = response.json()
    entity_ids = {item["id"] for item in body["entities"]}
    assert rule_id in entity_ids
    assert seller_id in entity_ids
    assert len(body["edges"]) == 1
    assert body["edges"][0]["predicate"] == "运费承担方"
    assert body["edges"][0]["dst_name"] == "卖家"


def test_list_graph_entities_supports_search(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_graph(admin_client, kb_id)

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/graph/entities", params={"q": "卖家"})
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["name"] == "卖家"


def test_list_graph_entities_empty_without_search(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_graph(admin_client, kb_id)

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/graph/entities")
    assert response.status_code == 200
    assert response.json() == []


def test_list_graph_entities_filters_by_predicate(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    rule_id, seller_id = _seed_graph(admin_client, kb_id)

    response = admin_client.get(
        f"/admin/knowledge-bases/{kb_id}/graph/entities",
        params={"predicate": "运费承担"},
    )
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "七天无理由" in names
    assert "卖家" in names


def test_list_graph_predicates(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_graph(admin_client, kb_id)

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/graph/predicates")
    assert response.status_code == 200
    assert response.json() == ["运费承担方"]


def test_graph_neighbors_returns_enriched_payload(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    rule_id, seller_id = _seed_graph(admin_client, kb_id)

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/graph/entities/{rule_id}/neighbors")
    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == rule_id
    assert len(body["edges"]) == 1
    assert body["edges"][0]["dst"] == seller_id
    assert body["edges"][0]["dst_name"] == "卖家"
    neighbor_ids = {item["id"] for item in body["entities"]}
    assert seller_id in neighbor_ids
