"""贷款理财域：加深既有产品要素谓词的话术覆盖（不加新谓词）。"""

from __future__ import annotations

import re

from akos.application.ingest.rule_extractor import RulePattern

# 银行对客产品页 / 说明书常见写法；命中产品名则 subject 用产品，否则「本产品」供 document_anchor。
_LOAN_PRODUCT = (
    r"(?P<product>个人(?:综合)?消费贷款|个人信用贷款|住房贷款|经营贷款|"
    r"[^\s，。；;：:\n]{2,20}(?:贷款|贷))"
)

LOAN_RULES: list[RulePattern] = [
    # —— 最高额度 ——
    (
        re.compile(_LOAN_PRODUCT + r"(?:的)?最高额度(?:为|可达|不超过|最高)?(?P<object>[^。；;\n]+)"),
        "__product__",
        "最高额度",
    ),
    (
        re.compile(r"最高额度(?:可达|为|不超过)\s*(?P<object>\d+(?:\.\d+)?\s*万?元?)"),
        "本产品",
        "最高额度",
    ),
    (
        re.compile(r"(?:单户)?贷款(?:金额|额度)不超过(?P<object>[^。；;\n]+)"),
        "本产品",
        "最高额度",
    ),
    (
        re.compile(r"最高授信\s*(?P<object>\d+\s*万)"),
        "本产品",
        "最高额度",
    ),
    (
        re.compile(r"授信额度(?:最高)?(?:为|可达|不超过)?(?P<object>\d+(?:\.\d+)?\s*万?元?)"),
        "本产品",
        "最高额度",
    ),
    (
        re.compile(r"额度上限(?:为|：|:)?\s*(?P<object>\d+(?:\.\d+)?\s*万?元?)"),
        "本产品",
        "最高额度",
    ),
    # —— 利率_年化 ——
    (
        re.compile(_LOAN_PRODUCT + r"(?:年化)?利率(?:为|约|低至|起)?(?P<object>[^。；;\n]+)"),
        "__product__",
        "利率_年化",
    ),
    (
        re.compile(r"年化利率(?:为|约|低至|起)?(?P<object>[^。；;\n%]*%?(?:起|－|-|~|至)[^。；;\n]*)"),
        "本产品",
        "利率_年化",
    ),
    (
        re.compile(r"年化利率(?:为|约|低至|起)?(?P<object>\d+(?:\.\d+)?%\s*(?:起)?)"),
        "本产品",
        "利率_年化",
    ),
    (
        re.compile(r"年化综合融资成本(?:为|：|:)?\s*(?P<object>[^。；;\n]+)"),
        "本产品",
        "利率_年化",
    ),
    (
        re.compile(r"贷款利率(?:按照|按)(?P<object>[^。；;\n]+)"),
        "本产品",
        "利率_年化",
    ),
    # —— 还款方式 ——
    (
        re.compile(_LOAN_PRODUCT + r"还款方式(?:为|包括|支持|：|:)?(?P<object>[^。；;\n]+)"),
        "__product__",
        "还款方式",
    ),
    (
        re.compile(
            r"还款方式(?:为|包括|支持|：|:)?(?P<object>等额本息|等额本金|先息后本|随借随还|"
            r"到期一次还本付息|按期付息任意还本|[^。；;\n]+)"
        ),
        "本产品",
        "还款方式",
    ),
    (
        re.compile(
            r"(?:可选择|可选|采用)(?P<object>按月等额本息|按月等额本金|等额本息|等额本金|"
            r"先息后本|随借随还)(?:等)?(?:还款方式)?"
        ),
        "本产品",
        "还款方式",
    ),
    # —— 适用客户 ——
    (
        re.compile(_LOAN_PRODUCT + r"适用(?:于)?客户(?P<object>[^。；;\n]+)"),
        "__product__",
        "适用客户",
    ),
    (
        re.compile(r"贷款对象[：:]\s*(?P<object>[^。；;\n]+)"),
        "本产品",
        "适用客户",
    ),
    (
        re.compile(
            r"适用(?:于)?(?:有(?:消费)?融资需求[，,]?)?(?P<object>年满\s*\d+\s*周岁[^。；;\n]*)"
        ),
        "本产品",
        "适用客户",
    ),
    (
        re.compile(r"适用于(?P<object>有消费融资需求[^。；;\n]*)"),
        "本产品",
        "适用客户",
    ),
    # —— 贷款期限 ——
    (
        re.compile(_LOAN_PRODUCT + r"(?:贷款)?期限(?:最长)?(?:不超过|为)?(?P<object>[^。；;\n]+)"),
        "__product__",
        "贷款期限",
    ),
    (
        re.compile(r"(?:贷款)?期限最长不超过(?P<object>[^。；;\n]+)"),
        "本产品",
        "贷款期限",
    ),
    (
        re.compile(r"授信期限最长不超过(?P<object>[^。；;\n]+)"),
        "本产品",
        "贷款期限",
    ),
    (
        re.compile(r"贷款期限(?:为|：|:)?\s*(?P<object>\d+\s*年(?:以内|（含）以内)?[^。；;\n]*)"),
        "本产品",
        "贷款期限",
    ),
    # —— 担保方式 ——
    (
        re.compile(_LOAN_PRODUCT + r"担保方式(?:为|采取|包括)?(?P<object>[^。；;\n]+)"),
        "__product__",
        "担保方式",
    ),
    (
        re.compile(r"担保方式(?:为|采取|包括)(?P<object>信用|抵押|质押|保证|[^。；;\n]+)"),
        "本产品",
        "担保方式",
    ),
    (
        re.compile(r"采取(?P<object>抵押、保证、信用|信用、抵押|抵押|保证|质押|信用)方式"),
        "本产品",
        "担保方式",
    ),
    (
        re.compile(r"采用(?P<object>信用)方式"),
        "本产品",
        "担保方式",
    ),
    # —— 贷款用途 ——
    (
        re.compile(_LOAN_PRODUCT + r"(?:可用于|用于)(?P<object>[^。；;\n]+)"),
        "__product__",
        "贷款用途",
    ),
    (
        re.compile(r"贷款用途[：:]\s*(?P<object>[^。；;\n]+)"),
        "本产品",
        "贷款用途",
    ),
    (
        re.compile(r"(?:必须有明确的消费用途|可用于)(?P<object>[^。；;\n]+)"),
        "本产品",
        "贷款用途",
    ),
    (
        re.compile(r"不得用于(?P<object>[^。；;\n]+)"),
        "本产品",
        "贷款用途",
    ),
    # —— 起息说明 ——
    (
        re.compile(r"起息(?:日|说明)?[：:]\s*(?P<object>[^。；;\n]+)"),
        "本产品",
        "起息说明",
    ),
    (
        re.compile(r"(?:自|从)(?P<object>贷款发放日|放款日|资金到账日)(?:起)?(?:开始)?计息"),
        "本产品",
        "起息说明",
    ),
    (
        re.compile(r"贷款划出日即为(?:实际)?贷款发放日[，,]?(?P<object>[^。；;\n]*)"),
        "本产品",
        "起息说明",
    ),
]


class LoanRuleExtractor:
    """贷款规则：若命中产品名则用产品作 subject，否则保留「本产品」供 document_anchor 绑定。"""

    def extract(self, text: str):
        from akos.domain.ports.compiler import ExtractedClaim

        claims: list[ExtractedClaim] = []
        for pattern, subject_template, predicate in LOAN_RULES:
            for match in pattern.finditer(text):
                obj = match.group("object").strip()
                if not obj:
                    continue
                if subject_template == "__product__" and "product" in match.groupdict() and match.group("product"):
                    subject = match.group("product").strip()
                else:
                    subject = subject_template
                start, end = match.span()
                claims.append(
                    ExtractedClaim(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        confidence=0.88,
                        quote=text[start:end],
                        start=start,
                        end=end,
                    )
                )
        return claims
