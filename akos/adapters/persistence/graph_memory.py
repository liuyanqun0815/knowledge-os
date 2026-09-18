from graph.ports import Edge, GraphPort


class InMemoryGraph:
    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.relations: list[Edge] = []

    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None:
        self.entities[entity_id] = {"type": type, **props}

    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None:
        self.relations.append(Edge(src=src, predicate=predicate, dst=dst, props=props))

    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]:
        if depth != 1:
            return []
        edges = [e for e in self.relations if e.src == entity_id]
        if predicates is not None:
            edges = [e for e in edges if e.predicate in predicates]
        return edges

    def list_entities(self) -> list[tuple[str, dict]]:
        return list(self.entities.items())

    def get_entity(self, entity_id: str) -> dict | None:
        return self.entities.get(entity_id)
