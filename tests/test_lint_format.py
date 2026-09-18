from __future__ import annotations

from datetime import datetime, timezone

from akos.application.lint.service import format_lint_report_human
from akos.application.lint.models import LintIssue, LintReport


def test_format_lint_report_human_lists_conflict():
    report = LintReport(
        kb_id="kb-1",
        checked_at=datetime.now(timezone.utc),
        issues=[
            LintIssue(
                code="conflict",
                severity="error",
                message="同一 Claim 族存在 2 条 active 记录，可能冲突",
                refs={"family_id": "family-conflict"},
            )
        ],
        summary={"conflict": 1},
    )

    text = format_lint_report_human(report)
    assert "conflict" in text
    assert "汇总: conflict=1" in text
