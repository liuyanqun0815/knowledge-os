from __future__ import annotations

from compiler.ports import ExtractedClaim

# 单槽互斥谓词：不同客体是版本覆盖，禁止合并。
EXCLUSIVE_PREDICATES = frozenset(
    {
        "运费承担方",
        "适用于",
        "适用类目",
        "适用客户",
        "利率_年化",
        "最高额度",
    }
)


def is_exclusive_predicate(predicate: str) -> bool:
    return predicate.strip() in EXCLUSIVE_PREDICATES


def _join_objects(parts: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = part.strip()
        if not text or text in seen:
            continue
        if any(text in existing and text != existing for existing in unique):
            continue
        unique = [existing for existing in unique if existing not in text]
        unique.append(text)
        seen.add(text)
    if any(len(item) > 8 or "，" in item or "。" in item for item in unique):
        return "；".join(unique)
    return "、".join(unique)


def _join_quotes(claims: list[ExtractedClaim]) -> tuple[str, int, int]:
    primary = next((claim for claim in claims if claim.quote.strip()), claims[0])
    return primary.quote, primary.start, primary.end


def merge_complementary_extracted(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    """Merge same subject+predicate objects unless the predicate is exclusive."""
    buckets: dict[tuple[str, str], list[ExtractedClaim]] = {}
    order: list[tuple[str, str]] = []
    for claim in claims:
        key = (claim.subject.strip(), claim.predicate.strip())
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(claim)

    merged: list[ExtractedClaim] = []
    for key in order:
        group = buckets[key]
        subject, predicate = key
        if is_exclusive_predicate(predicate) or len(group) == 1:
            merged.extend(group)
            continue
        quote, start, end = _join_quotes(group)
        merged.append(
            ExtractedClaim(
                subject=subject,
                predicate=predicate,
                object=_join_objects([item.object for item in group]),
                confidence=max(item.confidence for item in group),
                quote=quote,
                start=start,
                end=end,
            )
        )
    return merged
