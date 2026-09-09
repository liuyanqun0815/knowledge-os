from __future__ import annotations

from pathlib import Path

from knowledge.models import Source
from knowledge.ports import KnowledgePort

from infra.upload_utils import directory_from_relative, fuzzy_match, relative_path_from_kb_root


def build_source_response(source: Source, knowledge: KnowledgePort, kb_dir: Path) -> dict:
    relative_path = ""
    directory = "/"
    file_path = _resolve_source_path(source.uri)
    if file_path is not None:
        try:
            rel = relative_path_from_kb_root(file_path, kb_dir)
            relative_path = rel.as_posix()
            directory = directory_from_relative(rel)
        except ValueError:
            relative_path = source.title

    claims_count = len(knowledge.get_claims_for_source(source.id))
    return {
        "id": source.id,
        "title": source.title,
        "type": source.type,
        "uri": source.uri,
        "version": source.version,
        "created_at": source.created_at,
        "status": source.status,
        "relative_path": relative_path,
        "directory": directory,
        "claims_count": claims_count,
    }


def filter_sources_by_query(sources: list[dict], query: str | None) -> list[dict]:
    if not query:
        return sources
    return [
        source
        for source in sources
        if fuzzy_match(
            query,
            source.get("id", ""),
            source.get("title", ""),
            source.get("relative_path", ""),
            source.get("directory", ""),
        )
    ]


def _resolve_source_path(uri: str) -> Path | None:
    if not uri.startswith("file://"):
        return None
    raw = uri.removeprefix("file://")
    if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)
