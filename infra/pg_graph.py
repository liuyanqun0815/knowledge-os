from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from graph.ports import Edge


class PgGraph:
    """PostgreSQL graph repository scoped to a single knowledge base."""

    def __init__(self, engine: Engine, knowledge_base_id: str) -> None:
        self._engine = engine
        self._knowledge_base_id = knowledge_base_id

    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO entities (id, knowledge_base_id, type, props)
                    VALUES (:id, :knowledge_base_id, :type, CAST(:props AS jsonb))
                    ON CONFLICT (id) DO UPDATE SET
                        type = EXCLUDED.type,
                        props = EXCLUDED.props
                    WHERE entities.knowledge_base_id = EXCLUDED.knowledge_base_id
                    """),
                {
                    "id": entity_id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "type": type,
                    "props": json.dumps(props),
                },
            )

    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO relations (knowledge_base_id, src, predicate, dst, props)
                    VALUES (:knowledge_base_id, :src, :predicate, :dst, CAST(:props AS jsonb))
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "src": src,
                    "predicate": predicate,
                    "dst": dst,
                    "props": json.dumps(props),
                },
            )

    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]:
        if depth != 1:
            return []

        sql = """
            SELECT src, predicate, dst, props
            FROM relations
            WHERE knowledge_base_id = :knowledge_base_id
              AND src = :entity_id
        """
        params: dict[str, Any] = {
            "knowledge_base_id": self._knowledge_base_id,
            "entity_id": entity_id,
        }
        if predicates is not None:
            sql += " AND predicate = ANY(:predicates)"
            params["predicates"] = predicates

        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        edges: list[Edge] = []
        for row in rows:
            props = row.props
            if isinstance(props, str):
                props = json.loads(props)
            edges.append(Edge(src=row.src, predicate=row.predicate, dst=row.dst, props=dict(props)))
        return edges

    def _entity_from_row(self, entity_id: str, entity_type: str, props: Any) -> dict:
        if isinstance(props, str):
            props = json.loads(props)
        return {"type": entity_type, **dict(props)}

    def list_entities(self) -> list[tuple[str, dict]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, type, props
                    FROM entities
                    WHERE knowledge_base_id = :knowledge_base_id
                    """),
                {"knowledge_base_id": self._knowledge_base_id},
            ).fetchall()

        return [(row.id, self._entity_from_row(row.id, row.type, row.props)) for row in rows]

    def get_entity(self, entity_id: str) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT type, props
                    FROM entities
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND id = :entity_id
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "entity_id": entity_id,
                },
            ).fetchone()

        if row is None:
            return None
        return self._entity_from_row(entity_id, row.type, row.props)
