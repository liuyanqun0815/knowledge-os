"""企业文化域：加深倡导 / 禁止 / 适用于 的手册话术覆盖（不加新谓词）。"""

from __future__ import annotations

import re

from akos.application.ingest.rule_extractor import RulePattern

CULTURE_RULES: list[RulePattern] = [
    # —— 倡导 ——
    (
        re.compile(r"员工手册倡导(?P<object>[^。；;\n]+)"),
        "员工手册",
        "倡导",
    ),
    (
        re.compile(r"行为准则倡导(?P<object>[^。；;\n]+)"),
        "行为准则",
        "倡导",
    ),
    (
        re.compile(r"(?:公司|本手册|本准则|本指南)倡导(?P<object>[^。；;\n]+)"),
        "公司",
        "倡导",
    ),
    (
        re.compile(r"倡导员工(?P<object>[^。；;\n]+)"),
        "公司",
        "倡导",
    ),
    (
        re.compile(r"鼓励(?:员工)?(?P<object>诚信|协作|举报|相互尊重|[^。；;\n]{2,30})"),
        "公司",
        "倡导",
    ),
    (
        re.compile(r"诚信倡导(?P<object>[^。；;\n]+)"),
        "诚信",
        "倡导",
    ),
    (
        re.compile(r"(?:坚持|营造|践行)(?P<object>廉洁诚信|诚信合规|尊重包容|协作创新)(?:的)?"),
        "公司",
        "倡导",
    ),
    # —— 禁止 ——
    (
        re.compile(r"员工手册禁止(?P<object>[^。；;\n]+)"),
        "员工手册",
        "禁止",
    ),
    (
        re.compile(r"行为准则禁止(?P<object>[^。；;\n]+)"),
        "行为准则",
        "禁止",
    ),
    (
        re.compile(
            r"(?:严禁|禁止)(?P<object>贿赂|回扣|腐败|利益冲突|歧视|骚扰|"
            r"泄密|虚假记录|内幕交易|打击报复|侵占(?:公司)?财产|[^。；;\n]{2,40})"
        ),
        "员工手册",
        "禁止",
    ),
    (
        re.compile(
            r"不得(?P<object>从事任何形式的歧视|泄露(?:公司)?保密信息|"
            r"索取或接受(?:金钱|礼物|利益)|将(?:公司)?保密信息[^。；;\n]{0,20})"
        ),
        "员工手册",
        "禁止",
    ),
    (
        re.compile(r"反对(?P<object>歧视|骚扰|任何歧视|任何形式的歧视[^。；;\n]*)"),
        "员工手册",
        "禁止",
    ),
    (
        re.compile(r"严格禁止对(?P<object>举报人(?:或参与调查人员)?[^。；;\n]*)"),
        "员工手册",
        "禁止",
    ),
    # —— 适用于 ——
    (
        re.compile(r"(?:员工手册|行为准则|本手册|本准则|本指南)适用于(?P<object>[^。；;\n]+)"),
        "员工手册",
        "适用于",
    ),
    (
        re.compile(r"适用范围[：:]\s*(?P<object>[^。；;\n]+)"),
        "员工手册",
        "适用于",
    ),
    (
        re.compile(r"准则适用于(?P<object>[^。；;\n]+)"),
        "行为准则",
        "适用于",
    ),
]
