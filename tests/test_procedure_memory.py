from akos.adapters.persistence.memory_store import InMemoryMemoryStore
from memory.models import Procedure, Step


def test_remember_and_get_procedure_exact_name():
    memory_store = InMemoryMemoryStore()
    procedure = Procedure(
        id="proc-1",
        name="仅退款流程",
        steps=[
            Step(order=1, description="校验签收状态"),
            Step(order=2, description="判断原因码"),
        ],
        ontology_refs=["RefundRule"],
        domain="ecommerce_cs",
    )
    memory_store.remember_procedure(procedure)

    loaded = memory_store.get_procedure("仅退款流程")

    assert loaded is not None
    assert loaded.id == "proc-1"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].description == "校验签收状态"


def test_get_procedure_matches_question_keywords():
    memory_store = InMemoryMemoryStore()
    procedure = Procedure(
        id="proc-refund-only",
        name="仅退款流程",
        steps=[Step(order=1, description="校验签收状态")],
        ontology_refs=["RefundRule"],
        domain="ecommerce_cs",
    )
    memory_store.remember_procedure(procedure)

    loaded = memory_store.get_procedure("仅退款流程怎么走？")

    assert loaded is not None
    assert loaded.name == "仅退款流程"


def test_ask_returns_procedure_steps(seeded_kb_id):
    from infra.bootstrap import build_orchestrator_for_kb

    orch = build_orchestrator_for_kb(seeded_kb_id)
    answer = orch.ask("仅退款流程怎么走？")

    assert answer.procedure_id == "proc-refund-only"
    assert "流程：仅退款流程" in answer.text
    assert "1. 校验签收状态" in answer.text
    assert "2. 判断原因码" in answer.text
    assert "3. 创建退款单" in answer.text
