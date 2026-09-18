import re

from akos.domain.ports.compiler import ExtractedClaim, ExtractorPort

_EXTRACTION_RULES = [
    (
        re.compile(r"七天无理由适用类目为(?P<object>[^。\n]+)"),
        "七天无理由",
        "适用类目",
    ),
    (
        re.compile(r"(?P<object>定制商品)不适用七天无理由退货"),
        "七天无理由",
        "排除",
    ),
    (
        re.compile(r"七天无理由退货运费承担方为(?P<object>[^。\n]+)"),
        "七天无理由",
        "运费承担方",
    ),
]


class RuleExtractor:
    def extract(self, text: str) -> list[ExtractedClaim]:
        claims: list[ExtractedClaim] = []
        for pattern, subject, predicate in _EXTRACTION_RULES:
            for match in pattern.finditer(text):
                obj = match.group("object").strip()
                start, end = match.span()
                quote = text[start:end]
                claims.append(
                    ExtractedClaim(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        confidence=0.9,
                        quote=quote,
                        start=start,
                        end=end,
                    )
                )
        return claims
