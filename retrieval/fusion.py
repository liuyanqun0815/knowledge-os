from __future__ import annotations

from retrieval.ports import Hit

_RRF_K = 60


def rrf_score(rank: int, k: int = _RRF_K) -> float:
    return 1.0 / (k + rank)


def fuse_hits(claim_hits: list[Hit], chunk_hits: list[Hit], *, claim_weight: float = 0.5) -> list[Hit]:
    chunk_weight = 1.0 - claim_weight
    scores: dict[str, Hit] = {}
    totals: dict[str, float] = {}

    for rank, hit in enumerate(claim_hits):
        key = f"claim:{hit.claim_id or hit.snippet}"
        totals[key] = totals.get(key, 0.0) + rrf_score(rank) * claim_weight
        scores[key] = hit

    for rank, hit in enumerate(chunk_hits):
        key = f"chunk:{hit.chunk_id or hit.snippet}"
        totals[key] = totals.get(key, 0.0) + rrf_score(rank) * chunk_weight
        scores[key] = hit

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
