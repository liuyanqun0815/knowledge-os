from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^#{1,6}\s")
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


@dataclass(frozen=True)
class ChunkResult:
    chunks: list[str]
    truncated: bool


@dataclass(frozen=True)
class DocumentChunkDraft:
    chunk_index: int
    title: str | None
    text: str
    start: int
    end: int
    section_path: list[str]


@dataclass(frozen=True)
class DocumentChunkResult:
    chunks: list[DocumentChunkDraft]
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


def _heading_level(line: str) -> int:
    stripped = line.lstrip()
    if not stripped.startswith("#"):
        return 0
    level = 0
    for char in stripped:
        if char == "#":
            level += 1
        else:
            break
    return level if level <= 6 else 0


def detect_chunk_mode(text: str, *, min_level1_or_2: int = 2) -> str:
    """Return ``heading`` when enough H1/H2 headings exist, else ``general``."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not _HEADING_RE.match(stripped):
            continue
        level = _heading_level(stripped)
        if 1 <= level <= 2:
            count += 1
            if count >= min_level1_or_2:
                return "heading"
    return "general"


def _collect_heading_spans(
    text: str,
    *,
    heading_level: int = 2,
) -> list[tuple[int, int, list[str], str | None]]:
    """Split on headings with level <= heading_level; deeper headings stay inside the block."""
    if not text:
        return []

    split_level = max(1, min(6, heading_level))
    boundaries: list[tuple[int, str | None, list[str]]] = []
    section_path: list[str] = []
    pos = 0

    for line in text.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        stripped = line.strip()
        if not _HEADING_RE.match(stripped):
            continue
        level = _heading_level(stripped)
        if level == 0 or level > split_level:
            if level > 0:
                heading = stripped.lstrip("#").strip()
                section_path = section_path[: level - 1]
                section_path.append(heading)
            continue
        heading = stripped.lstrip("#").strip()
        section_path = section_path[: level - 1]
        section_path.append(heading)
        boundaries.append((line_start, heading or None, list(section_path)))

    if not boundaries:
        return [(0, len(text), [], None)]

    spans: list[tuple[int, int, list[str], str | None]] = []
    if boundaries[0][0] > 0:
        spans.append((0, boundaries[0][0], [], None))
    for index, (start, title, path) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        spans.append((start, end, path, title))
    return spans


def _collect_section_spans(text: str) -> list[tuple[int, int, list[str], str | None]]:
    if not text:
        return []

    spans: list[tuple[int, int, list[str], str | None]] = []
    section_path: list[str] = []
    section_start = 0
    current_title: str | None = None
    pos = 0

    for line in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(line)
        pos = line_end
        stripped = line.strip()

        if _HEADING_RE.match(stripped):
            if section_start < line_start:
                spans.append((section_start, line_start, list(section_path), current_title))
            level = _heading_level(stripped)
            heading = stripped.lstrip("#").strip()
            if level > 0:
                section_path = section_path[: level - 1]
                section_path.append(heading)
            current_title = heading or None
            section_start = line_start
        elif stripped == "" and section_start < line_start:
            spans.append((section_start, line_end, list(section_path), current_title))
            section_start = line_end
            current_title = None

    if section_start < len(text):
        spans.append((section_start, len(text), list(section_path), current_title))

    if not spans:
        return [(0, len(text), [], None)]
    return spans


def _split_span(
    text: str,
    start: int,
    end: int,
    section_path: list[str],
    title: str | None,
    max_chars: int,
) -> list[tuple[int, int, list[str], str | None]]:
    span_text = text[start:end]
    if len(span_text) <= max_chars:
        return [(start, end, section_path, title)]

    pieces: list[tuple[int, int, list[str], str | None]] = []
    offset = 0
    part_index = 0
    while offset < len(span_text):
        piece = span_text[offset : offset + max_chars]
        piece_start = start + offset
        piece_end = piece_start + len(piece)
        piece_title = title if part_index == 0 else None
        pieces.append((piece_start, piece_end, section_path, piece_title))
        offset += max_chars
        part_index += 1
    return pieces


def chunk_document(
    text: str,
    max_chars: int,
    max_chunks: int,
    *,
    mode: str = "general",
    heading_level: int = 2,
) -> DocumentChunkResult:
    if not text:
        return DocumentChunkResult(chunks=[], truncated=False)

    resolved_mode = mode
    if mode == "auto":
        resolved_mode = detect_chunk_mode(text)
    if resolved_mode == "heading":
        base_spans = _collect_heading_spans(text, heading_level=heading_level)
    else:
        base_spans = _collect_section_spans(text)

    raw_spans: list[tuple[int, int, list[str], str | None]] = []
    for start, end, section_path, title in base_spans:
        raw_spans.extend(_split_span(text, start, end, section_path, title, max_chars))

    truncated = len(raw_spans) > max_chunks
    if truncated:
        kept = raw_spans[: max_chunks - 1]
        overflow_start = raw_spans[max_chunks - 1][0]
        overflow_end = raw_spans[-1][1]
        overflow_path = raw_spans[max_chunks - 1][2]
        overflow_title = raw_spans[max_chunks - 1][3]
        raw_spans = kept + [(overflow_start, overflow_end, overflow_path, overflow_title)]

    drafts = [
        DocumentChunkDraft(
            chunk_index=index,
            title=title,
            text=text[start:end],
            start=start,
            end=end,
            section_path=section_path,
        )
        for index, (start, end, section_path, title) in enumerate(raw_spans)
    ]
    validate_chunk_coverage(text, drafts)
    return DocumentChunkResult(chunks=drafts, truncated=truncated)


def validate_chunk_coverage(text: str, chunks: list[DocumentChunkDraft]) -> None:
    if not text:
        return
    if not chunks:
        raise ValueError("chunk coverage failed: no chunks for non-empty text")
    ordered = sorted(chunks, key=lambda item: item.chunk_index)
    if ordered[0].start != 0:
        raise ValueError("chunk coverage failed: first chunk must start at 0")
    if ordered[-1].end != len(text):
        raise ValueError("chunk coverage failed: last chunk must end at text length")
    for left, right in zip(ordered, ordered[1:]):
        if left.end != right.start:
            raise ValueError("chunk coverage failed: gaps or overlaps between chunks")
    rebuilt = "".join(chunk.text for chunk in ordered)
    if rebuilt != text:
        raise ValueError("chunk coverage failed: concatenated text mismatch")


def estimate_token_count(text: str) -> int:
    """Rough token estimate for budget checks.

    Whitespace-separated languages use word-like matches. Continuous CJK text
    under-counts with that alone, so fall back to ~2 chars per token for CJK-heavy spans.
    """
    tokens = _TOKEN_PATTERN.findall(text)
    cjk_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    if cjk_chars >= max(1, len(text.strip()) // 3):
        return max(len(tokens), cjk_chars // 2)
    return len(tokens)
