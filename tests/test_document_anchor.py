from akos.application.ingest.document_anchor import resolve_document_anchor

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
    assert anchor == "青银理财成就系列（低波共享）2024 年109 期"
    assert "璀璨人生" not in anchor


def test_falls_back_to_full_name_when_short_missing():
    text = "产品名称\n青银理财璀璨人生成就系列人民币个人理财计划（低波共享）2024 年109 期\n"
    assert resolve_document_anchor(text) == (
        "青银理财璀璨人生成就系列人民币个人理财计划（低波共享）2024 年109 期"
    )


def test_falls_back_to_title_when_no_fields():
    assert resolve_document_anchor("无表格字段", title="某某理财产品说明书.md") == "某某理财产品说明书"


def test_returns_none_when_empty():
    assert resolve_document_anchor("", title=None) is None
    assert resolve_document_anchor("   ", title="  ") is None
