"""领域规则应彼此隔离，并对既有谓词的同义表述有更深覆盖。"""

from __future__ import annotations

from akos.application.ingest.rule_extractor import RuleExtractor
from akos.domains.corporate_culture.domain import CorporateCultureDomain
from akos.domains.ecommerce_cs.domain import EcommerceCsDomain
from akos.domains.generic.domain import GenericDomain
from akos.domains.loan_finance.domain import LoanFinanceDomain


def test_default_rule_extractor_is_empty():
    text = "定制商品不适用七天无理由退货。员工手册倡导诚信。"
    assert RuleExtractor().extract(text) == []
    assert RuleExtractor([]).extract(text) == []


def test_domains_extract_distinct_predicates():
    ecommerce_text = "定制商品不适用七天无理由退货。七天无理由退货运费承担方为买家。"
    loan_text = "个人信用贷款最高额度30万元。还款方式为等额本息。"
    culture_text = "员工手册倡导诚信协作。禁止贿赂。"

    ec = {c.predicate for c in EcommerceCsDomain().get_extractor().extract(ecommerce_text)}
    loan = {c.predicate for c in LoanFinanceDomain().get_extractor().extract(loan_text)}
    culture = {c.predicate for c in CorporateCultureDomain().get_extractor().extract(culture_text)}
    generic = GenericDomain().get_extractor().extract(ecommerce_text + culture_text)

    assert "排除" in ec and "运费承担方" in ec
    assert "最高额度" in loan and "还款方式" in loan
    assert "倡导" in culture and "禁止" in culture
    assert generic == []
    assert CorporateCultureDomain().get_extractor().extract(ecommerce_text) == []
    assert EcommerceCsDomain().get_extractor().extract(culture_text) == []


def test_ecommerce_rules_cover_paraphrases():
    text = """
    非定制商品可申请七日无理由退货。
    定作商品不支持无理由退货。
    自收到商品之日起7日内可以申请无理由退货。
    商品退回所产生的运费依法由消费者承担。
    退回的商品应当完好。
    本商品支持七天无理由退货。
    """
    preds = {c.predicate for c in EcommerceCsDomain().get_extractor().extract(text)}
    assert {
        "适用类目",
        "排除",
        "退货时限_天",
        "运费承担方",
        "需包装完好",
        "是否支持无理由退货",
    }.issubset(preds)


def test_loan_rules_cover_product_sheet_phrasing():
    text = """
    贷款对象：年满18周岁且不超过60周岁的具有完全民事行为能力的中国公民。
    单户贷款额度不超过200万元。
    年化利率3.15%起。
    贷款期限最长不超过五年。
    担保方式采取抵押、保证、信用方式。
    贷款可用于住房装修、购车、旅游。
    不得用于购房及股票投资。
    可选择等额本息、等额本金还款方式。
    自贷款发放日起计息。
    """
    preds = {c.predicate for c in LoanFinanceDomain().get_extractor().extract(text)}
    assert {
        "适用客户",
        "最高额度",
        "利率_年化",
        "贷款期限",
        "担保方式",
        "贷款用途",
        "还款方式",
        "起息说明",
    }.issubset(preds)


def test_culture_rules_cover_handbook_phrasing():
    text = """
    公司倡导廉洁诚信。
    鼓励员工相互尊重。
    不得泄露公司保密信息。
    严格禁止对举报人或参与调查人员进行打击报复。
    本准则适用于正式员工、实习生。
    适用范围：全体员工。
    """
    preds = {c.predicate for c in CorporateCultureDomain().get_extractor().extract(text)}
    assert {"倡导", "禁止", "适用于"}.issubset(preds)
