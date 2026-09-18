from datetime import datetime, timezone
from pathlib import Path

from akos.application.ingest.rule_extractor import RuleExtractor
from akos.application.ingest.service import KnowledgeCompiler
from akos.domains.ecommerce_cs.seed import register_ecommerce_cs
from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Source
from akos.adapters.ontology.memory import InMemoryOntology
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.domain.ports.retrieval import RetrievalMode


def test_rule_extractor_finds_claims():
    text = Path("tests/fixtures/refund_policy_v3.md").read_text(encoding="utf-8")
    extracted = RuleExtractor().extract(text)
    preds = {e.predicate for e in extracted}
    assert "适用类目" in preds
    assert "排除" in preds or "是否支持无理由退货" in preds


def test_compiler_ingest_writes_claim_graph_evidence():
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    src = Source(
        id="s1",
        title="退换货政策v3",
        type="policy",
        uri="tests/fixtures/refund_policy_v3.md",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(src)
    knowledge.save_source_text(src.id, Path("tests/fixtures/refund_policy_v3.md").read_text(encoding="utf-8"))
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor())
    report = compiler.ingest("s1")
    assert report.claims_created >= 1
    assert knowledge.get_active_claims("七天无理由")
    bundle = evidence.explain([c.id for c in knowledge.get_active_claims("七天无理由")])
    assert bundle.items


def test_compiler_indexes_claims_in_retrieval():
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    retrieval = HybridRetrieval(knowledge, graph)
    src = Source(
        id="s1",
        title="退换货政策v3",
        type="policy",
        uri="tests/fixtures/refund_policy_v3.md",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(src)
    knowledge.save_source_text(src.id, Path("tests/fixtures/refund_policy_v3.md").read_text(encoding="utf-8"))
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor(), retrieval)
    report = compiler.ingest("s1")
    assert report.claims_created >= 1
    hits = retrieval.search("定制商品 七天无理由", RetrievalMode.HYBRID, {})
    assert hits
