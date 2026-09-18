from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class WikiPageMeta:
    path: str
    title: str
    kind: str
    content_hash: str
    source_ids: list[str] = field(default_factory=list)
    updated_at: datetime | None = None
    hub: str | None = None
    role: str | None = None
    summary: str | None = None


def _meta_dir(wiki_root: Path) -> Path:
    return Path(wiki_root) / ".meta"


def _pages_meta_path(wiki_root: Path) -> Path:
    return _meta_dir(wiki_root) / "pages.json"


def _serialize_updated_at(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _parse_updated_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def load_pages_meta(wiki_root: Path | str) -> dict[str, WikiPageMeta]:
    path = _pages_meta_path(Path(wiki_root))
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    result: dict[str, WikiPageMeta] = {}
    for page_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        result[page_id] = WikiPageMeta(
            path=str(payload.get("path", "")),
            title=str(payload.get("title", "")),
            kind=str(payload.get("kind", "")),
            content_hash=str(payload.get("content_hash", "")),
            source_ids=list(payload.get("source_ids") or []),
            updated_at=_parse_updated_at(payload.get("updated_at")),
            hub=payload.get("hub"),
            role=payload.get("role"),
            summary=(str(payload["summary"]).strip() if payload.get("summary") else None),
        )
    return result


def save_pages_meta(wiki_root: Path | str, pages: dict[str, WikiPageMeta]) -> Path:
    root = Path(wiki_root)
    meta_dir = _meta_dir(root)
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = _pages_meta_path(root)
    payload = {}
    for page_id, meta in pages.items():
        entry = {
            "path": meta.path,
            "title": meta.title,
            "kind": meta.kind,
            "content_hash": meta.content_hash,
            "source_ids": list(meta.source_ids),
            "updated_at": _serialize_updated_at(meta.updated_at),
        }
        if meta.hub is not None:
            entry["hub"] = meta.hub
        if meta.role is not None:
            entry["role"] = meta.role
        if meta.summary:
            entry["summary"] = meta.summary
        payload[page_id] = entry
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
