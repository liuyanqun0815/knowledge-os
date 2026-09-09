from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from retrieval.ports import Hit, RetrievalMode, RetrievalPort

_GRAPH_RELATION_WORDS = ("关系", "关联", "之间", "相关")


def route_mode(question: str) -> RetrievalMode:
    if "为什么" in question or "为何" in question:
        return RetrievalMode.CLAIM
    if any(word in question for word in _GRAPH_RELATION_WORDS):
        return RetrievalMode.GRAPH
    return RetrievalMode.HYBRID


def retrieve(
    retrieval: RetrievalPort,
    question: str,
    mode: RetrievalMode,
    as_of: datetime | None = None,
) -> list[Hit]:
    filters: dict[str, Any] = {}
    if as_of is not None:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        filters["as_of"] = as_of
    return retrieval.search(question, mode, filters)
