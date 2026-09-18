from akos.application.ingest.claim_merge import is_exclusive_predicate, merge_complementary_extracted
from akos.domain.ports.compiler import ExtractedClaim
from akos.application.ingest.service import KnowledgeCompiler
from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from ontology.registry import InMemoryOntology
from akos.adapters.retrieval.hybrid import HybridRetrieval


def _claim(subject: str, predicate: str, obj: str, quote: str) -> ExtractedClaim:
    return ExtractedClaim(
        subject=subject,
        predicate=predicate,
        object=obj,
        confidence=0.9,
        quote=quote,
        start=0,
        end=len(quote),
    )


def test_is_exclusive_predicate_keeps_single_slot_facts() -> None:
    assert is_exclusive_predicate("运费承担方") is True
    assert is_exclusive_predicate("适用于") is True
    assert is_exclusive_predicate("保养方式") is False
    assert is_exclusive_predicate("要求") is False


def test_merge_complementary_joins_same_subject_predicate() -> None:
    merged = merge_complementary_extracted(
        [
            _claim("鞋子", "保养方式", "避免长时间暴晒、雨淋", "避免长时间暴晒、雨淋"),
            _claim("鞋子", "保养方式", "不同场合轮换穿着，延长寿命", "不同场合轮换穿着，延长寿命"),
            _claim("设备使用", "要求", "按说明书使用，避免超负荷", "按说明书使用，避免超负荷"),
            _claim("设备使用", "要求", "保持通风散热", "保持通风散热"),
        ]
    )

    by_key = {(item.subject, item.predicate): item for item in merged}
    assert len(merged) == 2
    assert "避免长时间暴晒、雨淋" in by_key[("鞋子", "保养方式")].object
    assert "不同场合轮换穿着" in by_key[("鞋子", "保养方式")].object
    assert "按说明书使用" in by_key[("设备使用", "要求")].object
    assert "保持通风散热" in by_key[("设备使用", "要求")].object


def test_merge_complementary_does_not_join_exclusive_predicates() -> None:
    merged = merge_complementary_extracted(
        [
            _claim("七天无理由", "运费承担方", "买家", "买家承担"),
            _claim("七天无理由", "运费承担方", "平台", "平台承担"),
        ]
    )

    assert len(merged) == 2
    assert {item.object for item in merged} == {"买家", "平台"}


class _UnusedExtractor:
    def extract(self, text: str) -> list[ExtractedClaim]:
        raise AssertionError("unused")


def test_apply_extracted_claims_merges_complementary_objects() -> None:
    text = "避免长时间暴晒、雨淋。不同场合轮换穿着，延长寿命。"
    ontology = InMemoryOntology()
    knowledge = InMemoryKnowledge()
    knowledge.save_source_text("s1", text)
    compiler = KnowledgeCompiler(
        ontology,
        knowledge,
        InMemoryGraph(),
        InMemoryEvidence(),
        _UnusedExtractor(),
        HybridRetrieval(knowledge, InMemoryGraph()),
    )

    report = compiler.apply_extracted_claims(
        "s1",
        [
            _claim("鞋子", "保养方式", "避免长时间暴晒、雨淋", "避免长时间暴晒、雨淋"),
            _claim("鞋子", "保养方式", "不同场合轮换穿着，延长寿命", "不同场合轮换穿着，延长寿命"),
        ],
        open_predicates=True,
    )

    claims = knowledge.get_claims_for_source("s1")
    assert report.claims_created == 1
    assert len(claims) == 1
    assert claims[0].status == "active"
    assert "暴晒" in claims[0].object
    assert "轮换穿着" in claims[0].object


def test_apply_extracted_claims_folds_complementary_into_existing_active() -> None:
    """Non-exclusive different objects merge into one active claim (no staging twin)."""
    from datetime import datetime, timezone

    from akos.application.ingest.service import _family_id
    from akos.domain.models.knowledge import Claim

    text = "手机银行申请。银行柜台申请。"
    ontology = InMemoryOntology()
    knowledge = InMemoryKnowledge()
    knowledge.save_source_text("s1", text)
    graph = InMemoryGraph()
    retrieval = HybridRetrieval(knowledge, graph)
    compiler = KnowledgeCompiler(
        ontology,
        knowledge,
        graph,
        InMemoryEvidence(),
        _UnusedExtractor(),
        retrieval,
    )
    existing = Claim(
        id="c-old",
        family_id=_family_id("信用卡分期", "申请方式", "Concept"),
        version=1,
        subject="信用卡分期",
        predicate="申请方式",
        object="手机银行申请",
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["old"],
    )
    knowledge.append_claim(existing)
    retrieval.index_claim(existing)

    report = compiler.apply_extracted_claims(
        "s1",
        [_claim("信用卡分期", "申请方式", "银行柜台申请", "银行柜台申请")],
        open_predicates=True,
    )

    assert report.claims_created == 1
    assert not knowledge.get_claims_by_status("staging")
    assert knowledge.get_claim("c-old").status == "superseded"
    actives = [c for c in knowledge.get_claims_by_status("active") if c.predicate == "申请方式"]
    assert len(actives) == 1
    assert "手机银行申请" in actives[0].object
    assert "银行柜台申请" in actives[0].object


def test_apply_extracted_claims_exclusive_still_stages_on_conflict() -> None:
    from datetime import datetime, timezone

    from akos.application.ingest.service import _family_id
    from akos.domain.models.knowledge import Claim

    text = "七天无理由的运费承担方是平台。"
    ontology = InMemoryOntology()
    ontology.register_entity("七天无理由", "Policy")
    ontology.register_entity("买家", "Party")
    ontology.register_entity("平台", "Party")
    ontology.register_predicate("Policy", "运费承担方", "Party")
    knowledge = InMemoryKnowledge()
    knowledge.save_source_text("s1", text)
    compiler = KnowledgeCompiler(
        ontology,
        knowledge,
        InMemoryGraph(),
        InMemoryEvidence(),
        _UnusedExtractor(),
        HybridRetrieval(knowledge, InMemoryGraph()),
    )
    knowledge.append_claim(
        Claim(
            id="c-old",
            family_id=_family_id("七天无理由", "运费承担方", "Party"),
            version=1,
            subject="七天无理由",
            predicate="运费承担方",
            object="买家",
            subject_type="Policy",
            object_type="Party",
            confidence=1.0,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["old"],
        )
    )

    report = compiler.apply_extracted_claims(
        "s1",
        [_claim("七天无理由", "运费承担方", "平台", "运费承担方是平台")],
    )

    assert report.claims_created == 1
    staging = knowledge.get_claims_by_status("staging")
    assert len(staging) == 1
    assert staging[0].object == "平台"
    assert knowledge.get_claim("c-old").status == "active"


def test_apply_extracted_claims_quarantines_low_confidence_before_merge() -> None:
    text = "公司倡导诚信经营。公司倡导持续学习。"
    knowledge = InMemoryKnowledge()
    knowledge.save_source_text("s1", text)
    compiler = KnowledgeCompiler(
        InMemoryOntology(),
        knowledge,
        InMemoryGraph(),
        InMemoryEvidence(),
        _UnusedExtractor(),
        HybridRetrieval(knowledge, InMemoryGraph()),
    )

    report = compiler.apply_extracted_claims(
        "s1",
        [
            ExtractedClaim(
                subject="公司",
                predicate="倡导",
                object="诚信经营",
                confidence=0.9,
                quote="公司倡导诚信经营",
                start=0,
                end=8,
            ),
            ExtractedClaim(
                subject="公司",
                predicate="倡导",
                object="持续学习",
                confidence=0.4,
                quote="公司倡导持续学习",
                start=9,
                end=17,
            ),
        ],
        min_confidence=0.5,
        open_predicates=True,
    )

    claims = knowledge.get_claims_for_source("s1")
    assert report.claims_created == 1
    assert len(claims) == 1
    assert claims[0].object == "诚信经营"
    quarantine = knowledge.list_quarantine()
    assert len(quarantine) == 1
    assert quarantine[0]["reason"] == "low_confidence"
    assert quarantine[0]["raw"]["object"] == "持续学习"
