from datetime import datetime, timezone

from akos.interfaces.api.admin_api.ingest_summary import build_ingest_summary, snapshot_active_by_subject
from akos.interfaces.api.admin_api.schemas import ZipUploadItemResponse
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim


def test_build_ingest_summary_reports_new_claims_and_subjects():
    knowledge = InMemoryKnowledge()
    before_active = snapshot_active_by_subject(knowledge)
    before_quarantine = len(knowledge.list_quarantine())

    knowledge.append_claim(
        Claim(
            id="claim-1",
            family_id="family-1",
            version=1,
            subject="七天无理由",
            predicate="运费承担方",
            object="买家",
            subject_type="RefundRule",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["policy-v3"],
        )
    )
    knowledge.append_claim(
        Claim(
            id="claim-2",
            family_id="family-2",
            version=1,
            subject="七天无理由",
            predicate="排除",
            object="定制商品",
            subject_type="RefundRule",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["policy-v3"],
        )
    )

    results = [
        ZipUploadItemResponse(
            source_id="policy-v3",
            path="/tmp/policy-v3.md",
            claims_created=2,
            entities_upserted=1,
            evidence_links=2,
            quarantined=0,
            errors=[],
        )
    ]

    summary = build_ingest_summary(knowledge, before_active, before_quarantine, results)

    assert summary is not None
    assert "新建 2 条 Claim" in summary
    assert "补充实体「七天无理由」2 条" in summary


def test_build_ingest_summary_includes_quarantine(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from akos.interfaces.api.main import create_app
    from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID
    from tests.conftest import ROOT

    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "false")
    monkeypatch.delenv("AKOS_LLM_API_KEY", raising=False)

    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    sample_md = ROOT / "tests" / "fixtures" / "refund_policy_v3.md"

    with sample_md.open("rb") as handle:
        response = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted_async"] is True
    assert body["ingest_summary"] == "已接收，后台编译中"
    assert body["results"][0]["claims_created"] == 0

    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert sources.status_code == 200
    listed = sources.json()
    assert len(listed) >= 1
    assert listed[0]["claims_count"] >= 1
