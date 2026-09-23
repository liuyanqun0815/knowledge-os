from datetime import datetime, timezone
from pathlib import Path

from akos.application.ingest.rule_extractor import RuleExtractor
from akos.application.ingest.service import KnowledgeCompiler
from akos.domain.ports.compiler import ExtractedClaim
from akos.domains.ecommerce_cs.domain import EcommerceCsDomain
from akos.domains.ecommerce_cs.rules import ECOMMERCE_RULES
from akos.domains.ecommerce_cs.seed import register_ecommerce_cs
from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Source
from akos.adapters.ontology.memory import InMemoryOntology
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.domain.ports.retrieval import RetrievalMode
from infra.settings import Settings


class _ConfiguredLlm:
    is_configured = True


def _ingest_with_rules_only(compiler: KnowledgeCompiler, source_id: str, *, staging: bool = False, monkeypatch):
    monkeypatch.setattr(
        "akos.application.ingest.intersect.extract_llm_claims_from_text",
        lambda *args, **kwargs: [],
    )
    return compiler.ingest(
        source_id,
        staging=staging,
        llm_client=_ConfiguredLlm(),
        domain=EcommerceCsDomain(),
        settings=Settings(llm_api_key="test"),
    )


def test_rule_extractor_finds_claims():
    text = Path("tests/fixtures/refund_policy_v3.md").read_text(encoding="utf-8")
    extracted = RuleExtractor(ECOMMERCE_RULES).extract(text)
    preds = {e.predicate for e in extracted}
    assert "适用类目" in preds
    assert "排除" in preds or "是否支持无理由退货" in preds


def test_compiler_ingest_writes_claim_graph_evidence(monkeypatch):
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
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor(ECOMMERCE_RULES))
    report = _ingest_with_rules_only(compiler, "s1", monkeypatch=monkeypatch)
    assert report.claims_created >= 1
    assert knowledge.get_active_claims("七天无理由")
    bundle = evidence.explain([c.id for c in knowledge.get_active_claims("七天无理由")])
    assert bundle.items


def test_compiler_indexes_claims_in_retrieval(monkeypatch):
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
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor(ECOMMERCE_RULES), retrieval)
    report = _ingest_with_rules_only(compiler, "s1", monkeypatch=monkeypatch)
    assert report.claims_created >= 1
    hits = retrieval.search("定制商品 七天无理由", RetrievalMode.HYBRID, {})
    assert hits


def test_ingest_open_registers_novel_predicate_from_llm(monkeypatch):
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    text = "商品完好，不影响二次销售。"
    src = Source(
        id="s-open",
        title="七天无理由退货",
        type="policy",
        uri="mem://open",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(src)
    knowledge.save_source_text(src.id, text)
    quote = "商品完好"
    llm_claim = ExtractedClaim(
        subject="七天无理由退货",
        predicate="适用条件",
        object="商品完好，不影响二次销售",
        confidence=0.95,
        quote=quote,
        start=text.index(quote),
        end=text.index(quote) + len(quote),
    )
    monkeypatch.setattr(
        "akos.application.ingest.service.select_hybrid_candidates",
        lambda text, **kwargs: [llm_claim],
    )
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor([]))
    report = compiler.ingest(
        src.id,
        llm_client=_ConfiguredLlm(),
        domain=EcommerceCsDomain(),
        settings=Settings(_env_file=None, llm_api_key="test", extract_open_predicates=True),
    )
    assert report.quarantined == 0
    assert report.claims_created == 1
    claims = knowledge.get_claims_for_source(src.id)
    assert len(claims) == 1
    assert claims[0].predicate == "适用条件"
    assert claims[0].subject == "七天无理由"
    assert onto.validate_claim("RefundRule", "适用条件", "Concept")


def test_ingest_closed_quarantines_novel_predicate_from_llm(monkeypatch):
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    knowledge = InMemoryKnowledge()
    text = "商品完好，不影响二次销售。"
    src = Source(
        id="s-closed",
        title="七天无理由退货",
        type="policy",
        uri="mem://closed",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(src)
    knowledge.save_source_text(src.id, text)
    quote = "商品完好"
    claim = ExtractedClaim(
        subject="七天无理由",
        predicate="适用条件",
        object="商品完好",
        confidence=0.95,
        quote=quote,
        start=0,
        end=len(quote),
    )
    monkeypatch.setattr(
        "akos.application.ingest.service.select_hybrid_candidates",
        lambda text, **kwargs: [claim],
    )
    compiler = KnowledgeCompiler(
        onto,
        knowledge,
        InMemoryGraph(),
        InMemoryEvidence(),
        RuleExtractor([]),
    )
    report = compiler.ingest(
        src.id,
        llm_client=_ConfiguredLlm(),
        domain=EcommerceCsDomain(),
        settings=Settings(_env_file=None, llm_api_key="test", extract_open_predicates=False),
    )
    assert report.claims_created == 0
    assert report.quarantined == 1
    assert knowledge.list_quarantine()[0]["reason"] == "invalid_predicate"
