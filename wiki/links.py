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
    """Legacy flat page id: ``topic-{name}``."""
    return f"topic-{sanitize_filename(name)}"


def topic_page_path(hub: str, leaf: str | None = None) -> str:
    """Hierarchy-relative page path without ``.md`` suffix."""
    hub_part = sanitize_filename(hub)
    if leaf is None:
        return f"{hub_part}/_index"
    return f"{hub_part}/{sanitize_filename(leaf)}"


def topic_wikilink(
    hub_or_name: str,
    leaf: str | None = None,
    label: str | None = None,
    *,
    hierarchy_enabled: bool = True,
) -> str:
    """Path-based wikilink when hierarchy is on; legacy ``topic-`` when off."""
    if not hierarchy_enabled:
        name = hub_or_name
        return f"[[{topic_page_name(name)}|{label or name}]]"
    path = topic_page_path(hub_or_name, leaf)
    if label is not None:
        display = label
    elif leaf is not None:
        display = leaf
    else:
        display = hub_or_name
    return f"[[{path}|{display}]]"


def chunk_page_name(source_id: str, chunk_index: int) -> str:
    return f"chunk-{sanitize_filename(source_id)}-{chunk_index}"


def chunk_wikilink(source_id: str, chunk_index: int, label: str) -> str:
    return f"[[{chunk_page_name(source_id, chunk_index)}|{label}]]"
