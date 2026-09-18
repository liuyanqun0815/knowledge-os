from datetime import datetime, timezone

from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim, Source
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.domain.ports.retrieval import RetrievalMode


def test_claim_and_bm25_search():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source("s1", "p", "policy", "u", "3", datetime.now(timezone.utc), "ready")
    )
    knowledge.save_source_text("s1", "七天无理由适用类目为非定制商品。定制商品不适用。")
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="适用类目",
        object="非定制商品",
        subject_type="RefundRule",
        object_type="Category",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)
    r = HybridRetrieval(knowledge, graph)
    r.index_claim(claim)
    hits = r.search("定制商品 七天无理由", RetrievalMode.HYBRID, {})
    assert hits
    assert any(h.claim_id == "c1" or "定制" in (h.snippet or "") for h in hits)


def test_graph_search_uses_graph_port_not_entities_dict():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    graph.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    graph.upsert_relation("e_rule", "适用类目", "e_cat", {})

    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="适用类目",
        object="非定制商品",
        subject_type="RefundRule",
        object_type="Category",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)

    r = HybridRetrieval(knowledge, graph)
    r.index_claim(claim)
    hits = r.search("七天无理由", RetrievalMode.GRAPH, {})
    assert hits
    assert hits[0].entity_id == "e_rule"


def test_graph_search_follows_two_hop_neighbors():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    graph.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    graph.upsert_entity("e_fee", "Concept", {"name": "买家"})
    graph.upsert_relation("e_rule", "适用类目", "e_cat", {})
    graph.upsert_relation("e_cat", "关联", "e_fee", {})

    claims = [
        Claim(
            id="c1",
            family_id="f1",
            version=1,
            subject="七天无理由",
            predicate="适用类目",
            object="非定制商品",
            subject_type="RefundRule",
            object_type="Category",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["s1"],
        ),
        Claim(
            id="c2",
            family_id="f2",
            version=1,
            subject="非定制商品",
            predicate="关联",
            object="买家",
            subject_type="Category",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["s1"],
        ),
    ]
    for claim in claims:
        knowledge.append_claim(claim)

    r = HybridRetrieval(knowledge, graph)
    for claim in claims:
        r.index_claim(claim)

    hits = r.search("七天无理由", RetrievalMode.GRAPH, {})
    snippets = " ".join(hit.snippet or "" for hit in hits)
    assert "适用类目" in snippets
    assert "关联" in snippets


def test_warm_index_rebuilds_from_persisted_active_claims():
    """重启后不应要求再次 compile：从 KnowledgePort 重建内存索引。"""
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    claim = Claim(
        id="c-holiday",
        family_id="f-holiday",
        version=1,
        subject="节假日",
        predicate="覆盖",
        object="春节、国庆等长假",
        subject_type="Policy",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)

    r = HybridRetrieval(knowledge, graph)
    assert r.search("节假日发货吗？", RetrievalMode.CLAIM, {}) == []

    r.warm_index()
    hits = r.search("节假日发货吗？", RetrievalMode.CLAIM, {})
    assert hits
    assert hits[0].claim_id == "c-holiday"
