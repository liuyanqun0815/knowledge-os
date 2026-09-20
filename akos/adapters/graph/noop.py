"""No-op GraphPort used when a knowledge base has graph_enabled=false."""

from __future__ import annotations

from akos.domain.ports.graph import Edge


class NoOpGraph:
    """Swallow writes and return empty reads — does not touch Postgres/Neo4j."""

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
