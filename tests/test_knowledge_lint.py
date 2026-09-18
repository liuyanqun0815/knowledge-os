from datetime import datetime, timezone

from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.application.lint.service import run_lint
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim, Source, TextSpan


def _source(source_id: str = "policy-v3", title: str = "refund_policy_v3.md") -> Source:
    return Source(
        id=source_id,
        title=title,
        type="policy",
        uri=f"file://{source_id}",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _claim(
    claim_id: str,
    family_id: str,
    *,
    status: str = "active",
    source_ids: list[str] | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        family_id=family_id,
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status=status,
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=source_ids or ["policy-v3"],
    )


def test_run_lint_reports_no_issues_on_healthy_kb():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("policy-v3", "七天无理由退货运费由买家承担。")
    claim = _claim("claim-1", "family-1")
    knowledge.append_claim(claim)
    evidence.bind(
        "claim-1",
        "policy-v3",
        TextSpan(source_id="policy-v3", start=0, end=10, quote="七天无理由退货运费由买家承担"),
        0.9,
    )

    report = run_lint(knowledge, evidence, "kb-healthy")

    assert report.kb_id == "kb-healthy"
    assert report.issues == []
    assert report.summary == {}


def test_run_lint_detects_conflict_in_same_family():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("policy-v3", "policy text")
    knowledge.append_claim(_claim("claim-a", "family-x"))
    knowledge.append_claim(
        Claim(
            id="claim-b",
            family_id="family-x",
            version=2,
            subject="七天无理由",
            predicate="运费承担方",
            object="平台",
            subject_type="RefundRule",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["policy-v3"],
        )
    )

    report = run_lint(knowledge, evidence, "kb-conflict")

    assert report.summary["conflict"] == 1
    assert report.issues[0].code == "conflict"
    assert report.issues[0].refs["family_id"] == "family-x"


def test_run_lint_detects_missing_evidence():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("policy-v3", "policy text")
    knowledge.append_claim(_claim("claim-1", "family-1"))

    report = run_lint(knowledge, evidence, "kb-missing-evidence")

    assert report.summary["missing_evidence"] == 1
    assert report.issues[0].refs["claim_id"] == "claim-1"


def test_run_lint_detects_span_mismatch_as_missing_evidence():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("policy-v3", "actual policy text")
    knowledge.append_claim(_claim("claim-1", "family-1"))
    evidence.bind(
        "claim-1",
        "policy-v3",
        TextSpan(source_id="policy-v3", start=0, end=5, quote="wrong quote"),
        0.9,
    )

    report = run_lint(knowledge, evidence, "kb-bad-span")

    assert report.summary["missing_evidence"] == 1


def test_run_lint_detects_orphan_source():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source("empty-doc", "empty.md"))

    report = run_lint(knowledge, evidence, "kb-orphan")

    assert report.summary["orphan_source"] == 1
    assert report.issues[0].refs["source_id"] == "empty-doc"


def test_run_lint_detects_quarantine_backlog():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.add_quarantine("invalid_predicate", {"subject": "测试", "predicate": "未知", "object": "值"})

    report = run_lint(knowledge, evidence, "kb-quarantine")

    assert report.summary["quarantine_backlog"] == 1
    assert report.issues[0].refs["count"] == "1"
