from compiler.document_anchor import resolve_document_anchor

SAMPLE = """
二、产品概述
产品名称
青银理财璀璨人生成就系列人民币个人理财计划（低波共享）2024 年109 期
产品简称
青银理财成就系列（低波共享）2024 年109 期
产品代码
CCCJGX24109
"""


def test_prefers_product_short_name():
    anchor = resolve_document_anchor(SAMPLE)
    assert anchor is not None
    assert "成就系列" in anchor
    assert "低波共享" in anchor


def test_falls_back_to_title_when_no_fields():
    assert resolve_document_anchor("无表格字段", title="某某理财产品说明书.md") == "某某理财产品说明书"


def test_returns_none_when_empty():
    assert resolve_document_anchor("", title=None) is None
    assert resolve_document_anchor("   ", title="  ") is None
