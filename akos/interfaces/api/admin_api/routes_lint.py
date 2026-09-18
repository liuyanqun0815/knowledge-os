from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import LintIssueResponse, LintReportResponse
from akos.interfaces.api.deps import build_orchestrator_for_request
from knowledge.lint import run_lint

router = APIRouter(prefix="/knowledge-bases", tags=["admin-lint"])


@router.get("/{kb_id}/lint", response_model=LintReportResponse)
def lint_knowledge_base(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> LintReportResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    report = run_lint(orchestrator.deps.knowledge, orchestrator.deps.evidence, kb_id)
    return LintReportResponse(
        kb_id=report.kb_id,
        checked_at=report.checked_at,
        summary=report.summary,
        issues=[
            LintIssueResponse(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                refs=issue.refs,
            )
            for issue in report.issues
        ],
    )
