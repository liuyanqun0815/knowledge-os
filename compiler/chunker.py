from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^#{1,6}\s")


@dataclass(frozen=True)
class ChunkResult:
    chunks: list[str]
    truncated: bool


def _split_sections(text: str) -> list[str]:
    if not text:
        return []

    sections: list[str] = []
    current: list[str] = []

    for line in text.splitlines():
        if _HEADING_RE.match(line):
            if current:
                section = "\n".join(current).strip()
                if section:
                    sections.append(section)
                current = []
            sections.append(line.strip())
        elif line.strip() == "":
            if current:
                section = "\n".join(current).strip()
                if section:
                    sections.append(section)
                current = []
        else:
            current.append(line)

    if current:
        section = "\n".join(current).strip()
        if section:
            sections.append(section)

    return sections


def _hard_split(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def chunk_text(text: str, max_chars: int, max_chunks: int) -> ChunkResult:
    normalized = text.strip()
    sections = _split_sections(normalized)
    chunks: list[str] = []
    for section in sections:
        chunks.extend(_hard_split(section, max_chars))

    truncated = len(chunks) > max_chunks
    if truncated:
        chunks = chunks[:max_chunks]

    return ChunkResult(chunks=chunks, truncated=truncated)
