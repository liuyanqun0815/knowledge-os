from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LintIssue:
    code: str
    severity: str
    message: str
    refs: dict[str, str] = field(default_factory=dict)


@dataclass
class LintReport:
    kb_id: str
    checked_at: datetime
    issues: list[LintIssue]
    summary: dict[str, int]
