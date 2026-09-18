from akos.domains.ecommerce_cs.seed import register_ecommerce_cs
from ontology.registry import InMemoryOntology


def test_ecommerce_seed_validates_refund_claim():
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    assert onto.normalize_term("7天无理由") == "七天无理由"
    assert onto.resolve_entity_type("七天无理由") == "RefundRule"
    assert onto.validate_claim("RefundRule", "适用类目", "Category") is True
    assert onto.validate_claim("RefundRule", "乱写关系", "Category") is False


def test_kernel_without_seed_degrades_to_concept():
    onto = InMemoryOntology()
    assert onto.resolve_entity_type("任意词") is None
    # 无种子时允许 Concept→任意谓词→Concept 降级策略
    assert onto.validate_claim("Concept", "相关", "Concept") is True
