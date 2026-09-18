from datetime import datetime, timezone

from akos.domain.ports.compiler import ExtractedClaim
from akos.application.ingest.service import KnowledgeCompiler, _family_id
from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim
from ontology.registry import InMemoryOntology
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.domain.ports.retrieval import RetrievalMode


class _UnusedExtractor:
    def extract(self, text: str) -> list[ExtractedClaim]:
        raise AssertionError("apply_extracted_claims must not invoke the extractor")


def _build_compiler(
    text: str = "七天无理由的运费承担方是买家。",
) -> tuple[
    KnowledgeCompiler,
    InMemoryKnowledge,
    InMemoryGraph,
    InMemoryEvidence,
    HybridRetrieval,
]:
    ontology = InMemoryOntology()
    ontology.register_entity("七天无理由", "Policy")
    ontology.register_entity("买家", "Party")
    ontology.register_entity("平台", "Party")
    ontology.register_predicate("Policy", "运费承担方", "Party")
    knowledge = InMemoryKnowledge()
    knowledge.save_source_text("source-1", text)
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    retrieval = HybridRetrieval(knowledge, graph)
    compiler = KnowledgeCompiler(ontology, knowledge, graph, evidence, _UnusedExtractor(), retrieval)
    return compiler, knowledge, graph, evidence, retrieval


def _extracted(
    *,
    obj: str = "买家",
    predicate: str = "运费承担方",
    confidence: float = 0.9,
    quote: str = "七天无理由的运费承担方是买家",
) -> ExtractedClaim:
    return ExtractedClaim(
        subject="七天无理由",
        predicate=predicate,
        object=obj,
        confidence=confidence,
        quote=quote,
        start=0,
        end=len(quote),
    )


def _append_existing_claim(knowledge: InMemoryKnowledge, *, obj: str = "买家") -> Claim:
    claim = Claim(
        id=f"existing-{obj}",
        family_id=_family_id("七天无理由", "运费承担方", "Party"),
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object=obj,
        subject_type="Policy",
        object_type="Party",
        confidence=1.0,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["old-source"],
    )
    knowledge.append_claim(claim)
    return claim


def test_apply_extracted_claims_quarantines_low_confidence():
    compiler, knowledge, graph, evidence, _ = _build_compiler()

    report = compiler.apply_extracted_claims("source-1", [_extracted(confidence=0.49)])

    assert report.quarantined == 1
    assert report.claims_created == 0
    assert knowledge.list_quarantine()[0]["reason"] == "low_confidence"
    assert not graph.entities
    assert not evidence.explain([]).items


def test_apply_extracted_claims_quarantines_quote_missing_from_source():
    compiler, knowledge, _, _, _ = _build_compiler()

    report = compiler.apply_extracted_claims("source-1", [_extracted(quote="原文中不存在")])

    assert report.quarantined == 1
    assert report.claims_created == 0
    assert knowledge.list_quarantine()[0]["reason"] == "span_missing"


def test_apply_extracted_claims_quarantines_invalid_predicate():
    compiler, knowledge, _, _, _ = _build_compiler(text="七天无理由支持未知关系买家。")

    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted(predicate="未知关系", quote="七天无理由支持未知关系买家")],
        open_predicates=False,
    )

    assert report.quarantined == 1
    entry = knowledge.list_quarantine()[0]
    assert entry["reason"] == "invalid_predicate"
    assert entry["raw"]["predicate"] == "未知关系"
    assert entry["raw"]["quote"] == "七天无理由支持未知关系买家"


def test_apply_extracted_claims_open_registers_and_writes_novel_predicate():
    compiler, knowledge, graph, evidence, retrieval = _build_compiler(
        text="七天无理由支持未知关系买家。"
    )
    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted(predicate="未知关系", quote="七天无理由支持未知关系买家")],
        open_predicates=True,
    )
    assert report.claims_created == 1
    assert report.quarantined == 0
    assert knowledge.list_quarantine() == []
    claim = next(c for c in knowledge.get_claims_by_status("active") if c.predicate == "未知关系")
    assert claim.subject == "七天无理由"
    assert compiler.ontology.validate_claim("Policy", "未知关系", "Party")
    hits = retrieval.search("未知关系", RetrievalMode.CLAIM, {})
    assert any(h.claim_id == claim.id for h in hits)


def test_apply_extracted_claims_skips_exact_spo_even_when_explicit_staging():
    """Same SPO must skip even if caller asks for staging — no active+staging twins."""
    compiler, knowledge, _, _, _ = _build_compiler()
    existing = _append_existing_claim(knowledge)

    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted()],
        staging=True,
    )

    assert report.claims_created == 0
    assert knowledge.get_claim_history(existing.family_id) == [existing]
    assert not knowledge.get_claims_by_status("staging")


def test_apply_extracted_claims_skips_existing_family_and_object():
    compiler, knowledge, graph, evidence, _ = _build_compiler()
    existing = _append_existing_claim(knowledge)

    report = compiler.apply_extracted_claims("source-1", [_extracted()])

    assert report.claims_created == 0
    assert report.quarantined == 0
    assert knowledge.get_claim_history(existing.family_id) == [existing]
    assert not graph.entities
    assert not evidence.explain([existing.id]).items


def test_apply_extracted_claims_stages_conflict_with_active_family():
    text = "七天无理由的运费承担方是平台。"
    compiler, knowledge, graph, evidence, retrieval = _build_compiler(text=text)
    existing = _append_existing_claim(knowledge)

    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted(obj="平台", quote="七天无理由的运费承担方是平台")],
    )

    history = knowledge.get_claim_history(existing.family_id)
    assert report.claims_created == 1
    assert len(history) == 2
    assert history[-1].status == "staging"
    assert history[-1].object == "平台"
    assert len(graph.entities) == 2
    assert evidence.explain([history[-1].id]).items
    assert retrieval.search("七天无理由 平台", RetrievalMode.CLAIM, {}) == []


def test_apply_extracted_claims_writes_and_indexes_active_claim():
    compiler, knowledge, graph, evidence, retrieval = _build_compiler()

    report = compiler.apply_extracted_claims("source-1", [_extracted()])

    claims = knowledge.get_active_claims("七天无理由", "运费承担方")
    assert report.claims_created == 1
    assert report.entities_upserted == 2
    assert report.evidence_links == 1
    assert len(claims) == 1
    assert claims[0].family_id == _family_id("七天无理由", "运费承担方", "Party")
    assert len(graph.entities) == 2
    assert len(graph.relations) == 1
    assert evidence.explain([claims[0].id]).items
    assert retrieval.search("七天无理由 买家", RetrievalMode.CLAIM, {})


def test_apply_extracted_claims_honors_explicit_staging_and_existing_skip_false():
    compiler, knowledge, _, _, retrieval = _build_compiler()
    existing = _append_existing_claim(knowledge)

    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted()],
        staging=True,
        existing_skip=False,
    )

    history = knowledge.get_claim_history(existing.family_id)
    assert report.claims_created == 1
    assert len(history) == 2
    assert history[-1].status == "staging"
    assert retrieval.search("七天无理由 买家", RetrievalMode.CLAIM, {}) == []


def test_apply_extracted_claims_reports_missing_source_text():
    compiler, _, _, _, _ = _build_compiler()

    report = compiler.apply_extracted_claims("missing", [_extracted()])

    assert report.errors == ["source text not found"]
    assert report.claims_created == 0
