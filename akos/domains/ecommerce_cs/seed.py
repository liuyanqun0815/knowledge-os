from akos.domain.ports.ontology import OntologyPort

ENTITY_SEEDS = {
    "七天无理由": "RefundRule",
    "非定制商品": "Category",
    "定制商品": "Category",
    "定作商品": "Category",
    "鲜活易腐": "Category",
    "数字化商品": "Category",
    "音像制品": "Category",
    "计算机软件": "Category",
    "报纸": "Category",
    "期刊": "Category",
    "退换货政策": "Policy",
    "买家": "Concept",
    "卖家": "Concept",
    "商家": "Concept",
    "经营者": "Concept",
    "平台": "Concept",
    "消费者": "Concept",
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
    "七日无理由": "七天无理由",
    "七天无理由退货": "七天无理由",
    "无理由退货": "七天无理由",
    "定作的商品": "定作商品",
    "消费者定作的商品": "定作商品",
    "鲜活易腐的商品": "鲜活易腐",
}


def register_ecommerce_cs(ontology: OntologyPort) -> None:
    for mention, etype in ENTITY_SEEDS.items():
        ontology.register_entity(mention, etype)
    for s, p, o in PREDICATES:
        ontology.register_predicate(s, p, o)
    for alias, canonical in ALIASES.items():
        ontology.register_alias(alias, canonical)
