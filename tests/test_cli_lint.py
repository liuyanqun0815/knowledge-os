from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from cli.main import app
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from tests.conftest import ROOT

SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


def test_lint_cli_json_after_ingest(tmp_path, monkeypatch):
    monkeypatch.setenv("AKOS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "false")
    monkeypatch.delenv("AKOS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)

    runner = CliRunner()
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    ingest_result = runner.invoke(app, ["ingest", str(SAMPLE_MD), "--kb", kb_id])
    assert ingest_result.exit_code == 0, ingest_result.stdout

    lint_result = runner.invoke(app, ["lint", "--kb", kb_id, "--format", "json"])
    assert lint_result.exit_code == 0, lint_result.stdout

    payload = json.loads(lint_result.stdout)
    assert payload["kb_id"] == kb_id
    assert "summary" in payload
    assert "issues" in payload
    assert "checked_at" in payload


def test_format_lint_report_human_lists_conflict():
    from knowledge.lint import format_lint_report_human
    from knowledge.lint_models import LintIssue, LintReport

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
