from __future__ import annotations

import re
from pathlib import Path

_SHORT = re.compile(
    r"产品简称\s*[:：]?\s*\n?\s*(?P<value>[^\n]+)",
    re.MULTILINE,
)
_FULL = re.compile(
    r"产品名称\s*[:：]?\s*\n?\s*(?P<value>[^\n]+)",
    re.MULTILINE,
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def resolve_document_anchor(text: str, title: str | None = None) -> str | None:
    body = text or ""
    for pattern in (_SHORT, _FULL):
        match = pattern.search(body)
        if match:
            value = _clean(match.group("value"))
            if value:
                return value
    if title:
        stem = Path(title).stem if "." in title else title.strip()
        stem = _clean(stem)
        if stem:
            return stem
    return None
