from __future__ import annotations

from akos.interfaces.api.admin_api.schemas import ZipUploadItemResponse
from knowledge.ports import KnowledgePort


def snapshot_active_by_subject(knowledge: KnowledgePort) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in knowledge.get_claims_by_status("active"):
        counts[claim.subject] = counts.get(claim.subject, 0) + 1
    return counts


def build_ingest_summary(
    knowledge: KnowledgePort,
    before_active_by_subject: dict[str, int],
    before_quarantine_count: int,
    results: list[ZipUploadItemResponse],
) -> str | None:
    """Build a rule-based Chinese summary for upload responses; no LLM."""
    total_claims = sum(item.claims_created for item in results)
    total_quarantined = sum(item.quarantined for item in results)
    after_active_by_subject = snapshot_active_by_subject(knowledge)
    after_quarantine_count = len(knowledge.list_quarantine())

    parts: list[str] = []
    if total_claims > 0:
        parts.append(f"新建 {total_claims} 条 Claim")

    for subject in sorted(after_active_by_subject):
        delta = after_active_by_subject[subject] - before_active_by_subject.get(subject, 0)
        if delta > 0:
            parts.append(f"补充实体「{subject}」{delta} 条")

    quarantine_delta = max(total_quarantined, after_quarantine_count - before_quarantine_count)
    if quarantine_delta > 0:
        parts.append(f"{quarantine_delta} 条进入 quarantine")

    if not parts:
        return None
    return "；".join(parts) + "。"
