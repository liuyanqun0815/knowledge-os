from dataclasses import dataclass
from typing import Protocol


@dataclass
class Edge:
    src: str
    predicate: str
    dst: str
    props: dict


class GraphPort(Protocol):
    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None: ...

    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None: ...

    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]: ...

    def list_entities(self) -> list[tuple[str, dict]]: ...

    def list_relations(self) -> list[Edge]: ...

    def get_entity(self, entity_id: str) -> dict | None: ...
