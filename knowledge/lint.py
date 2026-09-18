from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from akos.domain.ports.evidence import EvidencePort
from knowledge.lint_models import LintIssue, LintReport
from akos.domain.ports.knowledge import KnowledgePort

_SOURCE_CLAIM_STATUSES = frozenset({"active", "staging"})


def _claim_spans_verified(knowledge: KnowledgePort, evidence: EvidencePort, claim_id: str) -> bool:
    bundle = evidence.explain([claim_id])
    if not bundle.items:
        return False
    for item in bundle.items:
        source_text = knowledge.get_source_text(item["source_id"])
        if source_text is None or item["quote"] not in source_text:
            return False
    return True


def _check_conflicts(knowledge: KnowledgePort) -> list[LintIssue]:
    active_by_family: dict[str, list[str]] = defaultdict(list)
    for claim in knowledge.get_claims_by_status("active"):
        active_by_family[claim.family_id].append(claim.id)

    issues: list[LintIssue] = []
    for family_id, claim_ids in active_by_family.items():
        if len(claim_ids) <= 1:
            continue
        issues.append(
            LintIssue(
                code="conflict",
                severity="error",
                message=f"同一 Claim 族存在 {len(claim_ids)} 条 active 记录，可能冲突",
                refs={
                    "family_id": family_id,
                    "claim_ids": ",".join(sorted(claim_ids)),
                },
            )
        )
    return issues


def _check_missing_evidence(knowledge: KnowledgePort, evidence: EvidencePort) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for claim in knowledge.get_claims_by_status("active"):
        if _claim_spans_verified(knowledge, evidence, claim.id):
            continue
        issues.append(
            LintIssue(
                code="missing_evidence",
                severity="warning",
                message="active Claim 缺少有效 evidence 或原文 span 不匹配",
                refs={
                    "claim_id": claim.id,
                    "family_id": claim.family_id,
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                },
            )
        )
    return issues


def _check_orphan_sources(knowledge: KnowledgePort) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for source in knowledge.list_sources():
        claims = knowledge.get_claims_for_source(source.id)
        if any(claim.status in _SOURCE_CLAIM_STATUSES for claim in claims):
            continue
        issues.append(
            LintIssue(
                code="orphan_source",
                severity="warning",
                message="文档未关联任何 active/staging Claim",
                refs={"source_id": source.id, "title": source.title},
            )
        )
    return issues


def _check_quarantine_backlog(knowledge: KnowledgePort) -> list[LintIssue]:
    items = knowledge.list_quarantine()
    if not items:
        return []
    return [
        LintIssue(
            code="quarantine_backlog",
            severity="warning",
            message=f"隔离区待处理 {len(items)} 条",
            refs={"count": str(len(items))},
        )
    ]


def _build_summary(issues: list[LintIssue]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for issue in issues:
        summary[issue.code] += 1
    return dict(summary)


def run_lint(knowledge: KnowledgePort, evidence: EvidencePort, kb_id: str) -> LintReport:
    issues: list[LintIssue] = []
    issues.extend(_check_conflicts(knowledge))
    issues.extend(_check_missing_evidence(knowledge, evidence))
    issues.extend(_check_orphan_sources(knowledge))
    issues.extend(_check_quarantine_backlog(knowledge))
    return LintReport(
        kb_id=kb_id,
        checked_at=datetime.now(timezone.utc),
        issues=issues,
        summary=_build_summary(issues),
    )


def lint_report_to_dict(report: LintReport) -> dict:
    return {
        "kb_id": report.kb_id,
        "checked_at": report.checked_at.isoformat(),
        "summary": report.summary,
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "refs": issue.refs,
            }
            for issue in report.issues
        ],
    }


def format_lint_report_human(report: LintReport) -> str:
    lines = [f"知识库 {report.kb_id} Lint 报告（{report.checked_at.isoformat()}）"]
    if not report.issues:
        lines.append("未发现健康问题。")
        return "\n".join(lines)

    lines.append(f"共 {len(report.issues)} 项：")
    for issue in report.issues:
        refs = ", ".join(f"{key}={value}" for key, value in issue.refs.items())
        suffix = f" ({refs})" if refs else ""
        lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}{suffix}")

    summary = ", ".join(f"{key}={value}" for key, value in sorted(report.summary.items()))
    lines.append(f"汇总: {summary}")
    return "\n".join(lines)
