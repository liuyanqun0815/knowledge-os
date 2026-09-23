"""贷款理财域本体与实体种子。"""

from __future__ import annotations

from akos.domain.ports.ontology import OntologyPort

ENTITY_SEEDS = {
    "个人消费贷款": "Product",
    "个人综合消费贷款": "Product",
    "个人信用贷款": "Product",
    "住房贷款": "Product",
    "经营贷款": "Product",
    "等额本息": "RepaymentMethod",
    "等额本金": "RepaymentMethod",
    "先息后本": "RepaymentMethod",
    "随借随还": "RepaymentMethod",
    "到期一次还本付息": "RepaymentMethod",
    "信用": "GuaranteeType",
    "抵押": "GuaranteeType",
    "质押": "GuaranteeType",
    "保证": "GuaranteeType",
}

PREDICATES = [
    ("Product", "适用客户", "Concept"),
    ("Product", "利率_年化", "Concept"),
    ("Product", "最高额度", "Concept"),
    ("Product", "还款方式", "RepaymentMethod"),
    ("Product", "贷款期限", "Concept"),
    ("Product", "担保方式", "GuaranteeType"),
    ("Product", "贷款用途", "Concept"),
    ("Product", "起息说明", "Concept"),
]

ALIASES = {
    "消费贷": "个人消费贷款",
    "信用贷": "个人信用贷款",
    "房贷": "住房贷款",
    "年化利率": "利率_年化",
    "额度上限": "最高额度",
}


def register_loan_finance(ontology: OntologyPort) -> None:
    for mention, etype in ENTITY_SEEDS.items():
        ontology.register_entity(mention, etype)
    for subject_type, predicate, object_type in PREDICATES:
        ontology.register_predicate(subject_type, predicate, object_type)
    for alias, canonical in ALIASES.items():
        ontology.register_alias(alias, canonical)
