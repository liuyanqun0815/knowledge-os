from akos.domain.ports.ontology import OntologyPort

ENTITY_SEEDS = {
    "七天无理由": "RefundRule",
    "非定制商品": "Category",
    "定制商品": "Category",
    "退换货政策": "Policy",
    "买家": "Concept",
    "卖家": "Concept",
    "平台": "Concept",
}

PREDICATES = [
    ("RefundRule", "适用类目", "Category"),
    ("RefundRule", "排除", "Category"),
    ("RefundRule", "退货时限_天", "Concept"),
    ("RefundRule", "运费承担方", "Concept"),
    ("RefundRule", "需包装完好", "Concept"),
    ("RefundRule", "是否支持无理由退货", "Concept"),
    ("Policy", "引用", "RefundRule"),
    ("Policy", "覆盖", "Policy"),
    ("ShippingRule", "适用", "Category"),
    ("ShippingRule", "优先于", "ShippingRule"),
]

ALIASES = {
    "7天无理由": "七天无理由",
    "七天无理由退货": "七天无理由",
    "无理由退货": "七天无理由",
}


def register_ecommerce_cs(ontology: OntologyPort) -> None:
    for mention, etype in ENTITY_SEEDS.items():
        ontology.register_entity(mention, etype)
    for s, p, o in PREDICATES:
        ontology.register_predicate(s, p, o)
    for alias, canonical in ALIASES.items():
        ontology.register_alias(alias, canonical)
