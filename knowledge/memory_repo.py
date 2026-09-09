from datetime import datetime, timezone

from knowledge.models import Claim, Event, Source


class InMemoryKnowledge:
    def __init__(self) -> None:
        self._sources: dict[str, Source] = {}
        self._source_texts: dict[str, str] = {}
        self._claims: dict[str, Claim] = {}
        self._families: dict[str, list[str]] = {}
        self._quarantine: list[dict] = []
        self._events: list[Event] = []

    def save_source(self, source: Source) -> Source:
        self._sources[source.id] = source
        return source

    def get_source(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def list_sources(self) -> list[Source]:
        return list(self._sources.values())

    def save_source_text(self, source_id: str, text: str) -> None:
        self._source_texts[source_id] = text

    def get_source_text(self, source_id: str) -> str | None:
        return self._source_texts.get(source_id)

    def append_claim(self, claim: Claim) -> Claim:
        is_new = claim.id not in self._claims
        self._claims[claim.id] = claim
        if is_new:
            self._families.setdefault(claim.family_id, []).append(claim.id)
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def get_active_claims(self, subject: str, predicate: str | None = None) -> list[Claim]:
        result: list[Claim] = []
        for claim in self._claims.values():
            if claim.status != "active":
                continue
            if claim.subject != subject:
                continue
            if predicate is not None and claim.predicate != predicate:
                continue
            result.append(claim)
        return result

    def get_claim_history(self, claim_family_id: str) -> list[Claim]:
        claim_ids = self._families.get(claim_family_id, [])
        return [self._claims[cid] for cid in claim_ids if cid in self._claims]

    def mark_superseded(self, claim_id: str, valid_to: datetime | None = None) -> None:
        claim = self._claims.get(claim_id)
        if claim is None:
            return
        claim.status = "superseded"
        claim.valid_to = valid_to or datetime.now(timezone.utc)

    def get_claims_for_source(self, source_id: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if source_id in claim.source_ids]

    def get_claims_by_status(self, status: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.status == status]

    def as_of(self, query_time: datetime, family_id: str) -> Claim | None:
        claims = self.get_claim_history(family_id)
        candidates: list[Claim] = []
        for claim in claims:
            if claim.valid_from is not None and claim.valid_from > query_time:
                continue
            if claim.valid_to is not None and query_time >= claim.valid_to:
                continue
            candidates.append(claim)
        if not candidates:
            return None
        return max(candidates, key=lambda claim: claim.version)

    def add_quarantine(self, reason: str, raw: dict) -> None:
        self._quarantine.append({"reason": reason, "raw": raw})

    def list_quarantine(self) -> list[dict]:
        return list(self._quarantine)

    def append_event(self, event: Event) -> Event:
        self._events.append(event)
        return event

    def list_events(self, source_id: str | None = None) -> list[Event]:
        if source_id is None:
            return list(self._events)
        return [event for event in self._events if event.source_id == source_id]
