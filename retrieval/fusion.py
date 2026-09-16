from __future__ import annotations

from retrieval.ports import Hit

_RRF_K = 60


def rrf_score(rank: int, k: int = _RRF_K) -> float:
    return 1.0 / (k + rank)


def fuse_hits(
    claim_hits: list[Hit],
    chunk_hits: list[Hit],
    wiki_hits: list[Hit] | None = None,
    *,
    claim_weight: float = 0.5,
    wiki_weight: float = 0.9,
    chunk_weight: float | None = None,
) -> list[Hit]:
    """Fuse claim / wiki / chunk ranked lists with weighted RRF.

    Two-way callers that omit ``wiki_hits`` and ``chunk_weight`` keep the
    legacy split ``chunk_weight = 1.0 - claim_weight``.
    """
    wiki_list = wiki_hits or []
    if chunk_weight is None:
        if wiki_list:
            chunk_weight = 0.8
        else:
            chunk_weight = 1.0 - claim_weight

    scores: dict[str, Hit] = {}
    totals: dict[str, float] = {}

    def _accumulate(hits: list[Hit], prefix: str, weight: float) -> None:
        if weight <= 0:
            return
        for rank, hit in enumerate(hits):
            if prefix == "claim":
                key = f"claim:{hit.claim_id or hit.snippet}"
            elif prefix == "chunk":
                key = f"chunk:{hit.chunk_id or hit.snippet}"
            else:
                key = f"wiki:{hit.ref_id or hit.path or hit.snippet}"
            totals[key] = totals.get(key, 0.0) + rrf_score(rank) * weight
            scores[key] = hit

    _accumulate(claim_hits, "claim", claim_weight)
    _accumulate(wiki_list, "wiki", wiki_weight if wiki_list else 0.0)
    _accumulate(chunk_hits, "chunk", chunk_weight)

    fused: list[Hit] = []
    for key, total in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        hit = scores[key]
        fused.append(
            Hit(
                score=total,
                snippet=hit.snippet,
                hit_type=hit.hit_type,
                claim_id=hit.claim_id,
                chunk_id=hit.chunk_id,
                source_id=hit.source_id,
                entity_id=hit.entity_id,
                ref_id=hit.ref_id,
                title=hit.title,
                path=hit.path,
                content=hit.content,
            )
        )
    return fused


def route_fusion_weights(question: str) -> float:
    if any(word in question for word in ("为什么", "为何", "怎么", "如何", "流程", "步骤")):
        return 0.3
    if any(word in question for word in ("是什么", "多少", "谁", "何时", "什么时候")):
        return 0.7
    if any(word in question for word in ("关系", "关联", "之间", "相关", "影响", "涉及", "对应")):
        return 0.5
    return 0.5
