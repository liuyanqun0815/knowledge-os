"""graph_enabled=false 时使用的空实现 GraphPort。"""

from __future__ import annotations

from akos.domain.ports.graph import Edge


class NoOpGraph:
    """写入空操作、读返回空；不访问 Postgres/Neo4j。"""

    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None:
        return None

    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None:
        return None

    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]:
        return []

    def list_entities(self) -> list[tuple[str, dict]]:
        return []

    def list_relations(self) -> list[Edge]:
        return []

    def get_entity(self, entity_id: str) -> dict | None:
        return None
