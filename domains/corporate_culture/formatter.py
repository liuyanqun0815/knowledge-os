from knowledge.models import Claim


def format_corporate_claim(claim: Claim) -> str:
    if claim.predicate == "倡导":
        return f"{claim.subject}倡导{claim.object}"
    if claim.predicate == "禁止":
        return f"{claim.subject}禁止{claim.object}"
    if claim.predicate == "适用于":
        return f"{claim.subject}适用于{claim.object}"
    return f"{claim.subject}{claim.predicate}{claim.object}"
