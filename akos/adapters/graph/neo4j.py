from __future__ import annotations

from typing import Any

from akos.domain.ports.graph import Edge

_RELATIONSHIP_TYPE = "RELATES_TO"
_SYSTEM_REL_PROPS = frozenset({"predicate", "kb_id"})


class Neo4jGraph:
    """Neo4j GraphPort implementation scoped to a single knowledge base via kb_id."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        knowledge_base_id: str,
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._knowledge_base_id = knowledge_base_id
        self._driver: Any | None = None

    def _get_driver(self) -> Any:
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None:
        with self._get_driver().session() as session:
            session.run(
                """
                MERGE (n:Entity {id: $entity_id, kb_id: $kb_id})
                SET n.type = $type
                SET n += $props
                """,
                entity_id=entity_id,
                kb_id=self._knowledge_base_id,
                type=type,
                props=props,
            )

    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None:
        with self._get_driver().session() as session:
            session.run(
                f"""
                MERGE (src:Entity {{id: $src, kb_id: $kb_id}})
                MERGE (dst:Entity {{id: $dst, kb_id: $kb_id}})
                MERGE (src)-[r:{_RELATIONSHIP_TYPE} {{predicate: $predicate, kb_id: $kb_id}}]->(dst)
                SET r += $props
                """,
                src=src,
                dst=dst,
                predicate=predicate,
                kb_id=self._knowledge_base_id,
                props=props,
            )

    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]:
        if depth != 1:
            return []

        cypher = f"""
            MATCH (src:Entity {{id: $entity_id, kb_id: $kb_id}})-[r:{_RELATIONSHIP_TYPE} {{kb_id: $kb_id}}]->(dst:Entity {{kb_id: $kb_id}})
        """
        params: dict[str, Any] = {
            "entity_id": entity_id,
            "kb_id": self._knowledge_base_id,
        }
        if predicates is not None:
            cypher += " WHERE r.predicate IN $predicates"
            params["predicates"] = predicates
        cypher += " RETURN src.id AS src, r.predicate AS predicate, dst.id AS dst, properties(r) AS rprops"

        edges: list[Edge] = []
        with self._get_driver().session() as session:
            rows = session.run(cypher, **params)
            for record in rows:
                rel_props = dict(record["rprops"])
                for key in _SYSTEM_REL_PROPS:
                    rel_props.pop(key, None)
                edges.append(
                    Edge(
                        src=record["src"],
                        predicate=record["predicate"],
                        dst=record["dst"],
                        props=rel_props,
                    )
                )
        return edges

    def list_entities(self) -> list[tuple[str, dict]]:
        entities: list[tuple[str, dict]] = []
        with self._get_driver().session() as session:
            rows = session.run(
                """
                MATCH (n:Entity {kb_id: $kb_id})
                RETURN n.id AS id, n.type AS type, properties(n) AS props
                """,
                kb_id=self._knowledge_base_id,
            )
            for record in rows:
                props = dict(record["props"])
                for key in ("id", "kb_id", "type"):
                    props.pop(key, None)
                entities.append((record["id"], {"type": record["type"], **props}))
        return entities

    def get_entity(self, entity_id: str) -> dict | None:
        with self._get_driver().session() as session:
            record = session.run(
                """
                MATCH (n:Entity {id: $entity_id, kb_id: $kb_id})
                RETURN n.type AS type, properties(n) AS props
                """,
                entity_id=entity_id,
                kb_id=self._knowledge_base_id,
            ).single()
            if record is None:
                return None
            props = dict(record["props"])
            entity_type = record["type"]

        for key in ("id", "kb_id", "type"):
            props.pop(key, None)
        return {"type": entity_type, **props}
