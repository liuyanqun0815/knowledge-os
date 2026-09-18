from memory.models import Procedure, Step
from akos.domain.ports.memory import MemoryPort

REFUND_ONLY_PROCEDURE = Procedure(
    id="proc-refund-only",
    name="仅退款流程",
    steps=[
        Step(order=1, description="校验签收状态"),
        Step(order=2, description="判断原因码"),
        Step(order=3, description="创建退款单"),
    ],
    ontology_refs=["RefundRule"],
    domain="ecommerce_cs",
)


def seed_ecommerce_procedures(memory: MemoryPort) -> None:
    memory.remember_procedure(REFUND_ONLY_PROCEDURE)
