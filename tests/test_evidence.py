from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from knowledge.models import TextSpan


def test_bind_and_explain():
    ev = InMemoryEvidence()
    ev.bind("c1", "s1", TextSpan("s1", 0, 12, "定制商品不适用"), 0.95)
    bundle = ev.explain(["c1"])
    assert bundle.confidence >= 0.9
    assert bundle.items[0]["quote"] == "定制商品不适用"
