from __future__ import annotations

_UNSAFE_FILENAME_CHARS = ("/", "\\", ":", "*", "?", '"', "<", ">", "|")


def sanitize_filename(name: str) -> str:
    result = name
    for char in _UNSAFE_FILENAME_CHARS:
        result = result.replace(char, "_")
    result = result.strip()
    return result or "unnamed"


def source_page_name(source_id: str) -> str:
    return f"source-{sanitize_filename(source_id)}"


def source_wikilink(source_id: str, title: str | None = None) -> str:
    page = source_page_name(source_id)
    label = title or source_id
    return f"[[{page}|{label}]]"


def entity_page_name(subject: str) -> str:
    return sanitize_filename(subject)


def entity_wikilink(subject: str) -> str:
    return f"[[{entity_page_name(subject)}|{subject}]]"


def topic_page_name(name: str) -> str:
    return f"topic-{sanitize_filename(name)}"


def topic_wikilink(name: str) -> str:
    return f"[[{topic_page_name(name)}|{name}]]"


def chunk_page_name(source_id: str, chunk_index: int) -> str:
    return f"chunk-{sanitize_filename(source_id)}-{chunk_index}"


def chunk_wikilink(source_id: str, chunk_index: int, label: str) -> str:
    return f"[[{chunk_page_name(source_id, chunk_index)}|{label}]]"
