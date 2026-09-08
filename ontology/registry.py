class InMemoryOntology:
    def __init__(self) -> None:
        self._types: dict[str, str] = {}
        self._aliases: dict[str, str] = {}
        self._predicates: set[tuple[str, str, str]] = set()

    def register_entity(self, mention: str, entity_type: str) -> None:
        self._types[mention] = entity_type

    def register_predicate(self, subject_type: str, predicate: str, object_type: str) -> None:
        self._predicates.add((subject_type, predicate, object_type))

    def register_alias(self, alias: str, canonical: str) -> None:
        self._aliases[alias] = canonical

    def normalize_term(self, raw: str) -> str:
        return self._aliases.get(raw, raw)

    def resolve_entity_type(self, mention: str) -> str | None:
        mention = self.normalize_term(mention)
        return self._types.get(mention)

    def allowed_predicates(self, subject_type: str, object_type: str) -> list[str]:
        return sorted({p for s, p, o in self._predicates if s == subject_type and o == object_type})

    def validate_claim(self, subject_type: str, predicate: str, object_type: str) -> bool:
        if subject_type == "Concept" and object_type == "Concept":
            return True
        return (subject_type, predicate, object_type) in self._predicates
