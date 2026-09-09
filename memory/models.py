from dataclasses import dataclass, field


@dataclass
class Step:
    order: int
    description: str
    claim_refs: list[str] = field(default_factory=list)


@dataclass
class Procedure:
    id: str
    name: str
    steps: list[Step]
    ontology_refs: list[str]
    domain: str
