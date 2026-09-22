from __future__ import annotations

from akos.domain.ports.compiler import ExtractedClaim

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


def _split_object_parts(value: str) -> list[str]:
    """只按我们写出的分号（；或 ;）切开，不把值内部的顿号（、）当分隔符。"""
    text = value.strip()
    if not text:
        return []
    for sep in ("；", ";"):
        if sep in text:
            return [part.strip() for part in text.split(sep) if part.strip()]
    return [text]


def _join_objects(parts: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for piece in _split_object_parts(part):
            text = piece.strip()
            if not text or text in seen:
                continue
            if any(text in existing and text != existing for existing in unique):
                continue
            unique = [existing for existing in unique if existing not in text]
            unique.append(text)
            seen.add(text)
    # 短词用顿号；长句或已含标点的用分号。
    if any(len(item) > 8 or "，" in item or "。" in item or "、" in item for item in unique):
        return "；".join(unique)
    return "、".join(unique)


def join_claim_objects(*parts: str) -> str:
    """对外：去重并拼接可互补的 object 值。"""
    return _join_objects(list(parts))


def _join_quotes(claims: list[ExtractedClaim]) -> tuple[str, int, int]:
    primary = next((claim for claim in claims if claim.quote.strip()), claims[0])
    return primary.quote, primary.start, primary.end


def merge_complementary_extracted(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    """合并相同 subject+predicate 的 object；互斥谓词不合并。"""
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
