from __future__ import annotations

from akos.domain.models.knowledge import Claim


def format_ecommerce_claim(claim: Claim) -> str:
    if claim.predicate == "排除":
        return f"{claim.object}不适用{claim.subject}"
    if claim.predicate == "适用类目":
        return f"{claim.subject}适用类目为{claim.object}"
    if claim.predicate == "运费承担方":
        return f"{claim.subject}运费承担方为{claim.object}"
    if claim.predicate == "退货时限_天":
        return f"{claim.subject}退货时限为{claim.object}天"
    if claim.predicate == "需包装完好":
        return f"{claim.subject}要求{claim.object}"
    if claim.predicate == "是否支持无理由退货":
        return f"{claim.subject}{claim.object}无理由退货"
    return f"{claim.subject}{claim.predicate}{claim.object}"
