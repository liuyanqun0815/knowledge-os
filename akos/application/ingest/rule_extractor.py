"""确定性规则抽取：由领域注入规则列表，避免跨域串用。"""

from __future__ import annotations

import re
from collections.abc import Sequence

from akos.domain.ports.compiler import ExtractedClaim

# (pattern, subject, predicate)；pattern 须含命名组 object
RulePattern = tuple[re.Pattern[str], str, str]


class RuleExtractor:
    """按注入的正则规则抽 Claim；未注入时不做任何匹配。"""

    def __init__(self, rules: Sequence[RulePattern] | None = None) -> None:
        self._rules: list[RulePattern] = list(rules or ())

    def extract(self, text: str) -> list[ExtractedClaim]:
        claims: list[ExtractedClaim] = []
        for pattern, subject, predicate in self._rules:
            for match in pattern.finditer(text):
                obj = match.group("object").strip()
                if not obj:
                    continue
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
