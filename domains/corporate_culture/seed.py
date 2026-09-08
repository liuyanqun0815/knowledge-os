from ontology.ports import OntologyPort

ENTITY_SEEDS = {
    "诚信": "Value",
    "协作": "Value",
    "客户第一": "Value",
    "加班文化": "Behavior",
    "内部竞争": "Behavior",
    "员工手册": "Policy",
    "行为准则": "Policy",
    "研发部": "Department",
    "人力资源部": "Department",
}

PREDICATES = [
    ("Value", "倡导", "Behavior"),
    ("Value", "倡导", "Value"),
    ("Policy", "禁止", "Behavior"),
    ("Policy", "适用于", "Department"),
    ("Policy", "适用于", "Behavior"),
]

ALIASES = {
    "价值观": "诚信",
    "文化手册": "员工手册",
}


def register_corporate_culture(ontology: OntologyPort) -> None:
    for mention, entity_type in ENTITY_SEEDS.items():
        ontology.register_entity(mention, entity_type)
    for subject_type, predicate, object_type in PREDICATES:
        ontology.register_predicate(subject_type, predicate, object_type)
    for alias, canonical in ALIASES.items():
        ontology.register_alias(alias, canonical)
