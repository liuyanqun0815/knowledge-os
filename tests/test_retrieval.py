from datetime import datetime, timezone

from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim, Source
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


def test_graph_search_prefers_specific_seeds_and_shares_top_k():
    """短泛化种子（如「银行」）不得占满 top_k，对比问句应两侧产品都有命中。"""
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    # Insert generic seed first so list_entities order would starve specific products
    # under naive "first seed fills top_k" walk. 「银行」len=2 会被过滤；用「贷款产品」作噪声。
    graph.upsert_entity("e_noise", "Concept", {"name": "贷款产品"})
    for i in range(8):
        oid = f"e_noise_obj_{i}"
        graph.upsert_entity(oid, "Concept", {"name": f"贷款产品事项{i}"})
        graph.upsert_relation("e_noise", f"办理{i}", oid, {})

    graph.upsert_entity("e_cmb", "Concept", {"name": "招商银行闪电贷"})
    graph.upsert_entity("e_cmb_limit", "Concept", {"name": "闪电贷额度100万"})
    graph.upsert_relation("e_cmb", "最高贷款额度可达", "e_cmb_limit", {})

    graph.upsert_entity("e_icbc", "Concept", {"name": "融e借"})
    graph.upsert_entity("e_icbc_limit", "Concept", {"name": "融e借额度20万"})
    graph.upsert_relation("e_icbc", "贷款额度最高可达", "e_icbc_limit", {})

    # Topic duplicate should not double-count or drown Concept edges.
    graph.upsert_entity("topic:cmb", "Topic", {"name": "招商银行闪电贷"})
    graph.upsert_relation("topic:cmb", "涵盖", "e_cmb_limit", {})

    r = HybridRetrieval(knowledge, graph)
    detail = r.search_graph_detail("招商银行闪电贷比融e借额度高吗", top_k=6)
    snippets = " ".join(item.snippet or "" for item in detail)
    assert "招商银行闪电贷" in snippets
    assert "融e借" in snippets
    assert detail  # non-empty


def test_graph_search_drops_seeds_with_name_len_le_2():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    graph.upsert_entity("e_bank", "Concept", {"name": "银行"})
    graph.upsert_entity("e_bank_obj", "Concept", {"name": "无关事项"})
    graph.upsert_relation("e_bank", "办理", "e_bank_obj", {})
    graph.upsert_entity("e_cmb", "Concept", {"name": "招商银行闪电贷"})
    graph.upsert_entity("e_limit", "Concept", {"name": "100万元"})
    graph.upsert_relation("e_cmb", "最高贷款额度可达", "e_limit", {})

    r = HybridRetrieval(knowledge, graph)
    detail = r.search_graph_detail("招商银行闪电贷额度", top_k=10)
    snippets = " ".join(item.snippet or "" for item in detail)
    assert "招商银行闪电贷" in snippets
    assert "无关事项" not in snippets


def test_graph_mode_uses_dynamic_budget_per_seed():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    graph.upsert_entity("e_cmb", "Concept", {"name": "招商银行闪电贷"})
    for i in range(25):
        oid = f"e_obj_{i}"
        graph.upsert_entity(oid, "Concept", {"name": f"属性{i}"})
        graph.upsert_relation("e_cmb", f"有属性{i}", oid, {})

    r = HybridRetrieval(knowledge, graph)
    # 1 seed → min(20, 1*4) = 4
    hits = r.search("招商银行闪电贷怎么样", RetrievalMode.GRAPH, {})
    assert len(hits) == 4

    detail = r.search_graph_detail(
        "招商银行闪电贷怎么样",
        top_k=20,
        max_seeds=7,
        per_seed=4,
    )
    assert len(detail) == 4


def test_graph_dynamic_budget_scales_with_seed_count():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    products = ["招商银行闪电贷", "交通银行惠民贷", "融e借"]
    for name in products:
        eid = f"e_{name}"
        graph.upsert_entity(eid, "Concept", {"name": name})
        for i in range(6):
            oid = f"{eid}_o{i}"
            graph.upsert_entity(oid, "Concept", {"name": f"{name}属性{i}"})
            graph.upsert_relation(eid, f"有{i}", oid, {})

    r = HybridRetrieval(knowledge, graph)
    query = "、".join(products) + "哪个额度最高"
    detail = r.search_graph_detail(query, top_k=20, max_seeds=7, per_seed=4)
    # 3 seeds → min(20, 12) = 12
    assert len(detail) == 12
    by_src: dict[str, int] = {}
    for item in detail:
        by_src[item.src] = by_src.get(item.src, 0) + 1
    assert all(count <= 4 for count in by_src.values())


def test_graph_search_keeps_at_most_seven_longest_seeds():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    # 8 seeds of increasing length; only the 7 longest should remain.
    for i in range(8):
        name = "产品" + ("长" * (i + 1))
        eid = f"e_{i}"
        oid = f"o_{i}"
        graph.upsert_entity(eid, "Concept", {"name": name})
        graph.upsert_entity(oid, "Concept", {"name": f"属性{i}"})
        graph.upsert_relation(eid, "有", oid, {})

    query = "、".join("产品" + ("长" * (i + 1)) for i in range(8))
    r = HybridRetrieval(knowledge, graph)
    detail = r.search_graph_detail(query, top_k=20, max_seeds=7)
    src_names = {item.snippet.split(" ", 1)[0] for item in detail if item.snippet}
    assert "产品长" not in src_names  # shortest dropped
    assert "产品长长长长长长长长" in src_names  # longest kept
    assert len(src_names) <= 7


def test_hybrid_dedupes_claim_and_graph_and_skips_top_k_truncate():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    graph.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    graph.upsert_relation("e_rule", "适用类目", "e_cat", {})

    now = datetime.now(timezone.utc)
    claims = []
    for i in range(12):
        claim = Claim(
            id=f"c{i}",
            family_id=f"f{i}",
            version=1,
            subject="七天无理由",
            predicate=f"规则{i}",
            object=f"对象{i}",
            subject_type="RefundRule",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=now,
            valid_to=None,
            source_ids=["s1"],
        )
        claims.append(claim)
        knowledge.append_claim(claim)

    # Same SPO as the graph edge — should collapse with the graph hit.
    shared = Claim(
        id="c-shared",
        family_id="f-shared",
        version=1,
        subject="七天无理由",
        predicate="适用类目",
        object="非定制商品",
        subject_type="RefundRule",
        object_type="Category",
        confidence=0.9,
        status="active",
        valid_from=now,
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(shared)
    claims.append(shared)

    r = HybridRetrieval(knowledge, graph)
    for claim in claims:
        r.index_claim(claim)

    hits = r.search("七天无理由", RetrievalMode.HYBRID, {"top_k": 8, "graph_top_k": 20})
    assert len(hits) > 8  # hybrid no longer truncates by retrieval_top_k

    shared_hits = [hit for hit in hits if (hit.snippet or "").find("适用类目") >= 0]
    assert len(shared_hits) == 1
    assert shared_hits[0].claim_id == "c-shared"
    assert shared_hits[0].entity_id == "e_rule"


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
