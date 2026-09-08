from datetime import datetime, timezone

from graph.memory_repo import InMemoryGraph
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source
from retrieval.hybrid import HybridRetrieval
from retrieval.ports import RetrievalMode


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
