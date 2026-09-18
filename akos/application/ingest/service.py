from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING, Any

from compiler.ports import CompileReport, ExtractedClaim, ExtractorPort
from akos.application.ingest.claim_merge import is_exclusive_predicate, join_claim_objects, merge_complementary_extracted
from akos.application.ingest.intersect import select_hybrid_candidates
from evidence.ports import EvidencePort
from graph.ports import GraphPort
from knowledge.models import Claim, TextSpan
from knowledge.ports import KnowledgePort
from ontology.ports import OntologyPort

if TYPE_CHECKING:
    from retrieval.ports import RetrievalPort


def _family_id(subject: str, predicate: str, object_type: str) -> str:
    raw = f"{subject}|{predicate}|{object_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _entity_id(name: str, entity_type: str) -> str:
    raw = f"{entity_type}:{name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class KnowledgeCompiler:
    def __init__(
        self,
        ontology: OntologyPort,
        knowledge: KnowledgePort,
        graph: GraphPort,
        evidence: EvidencePort,
        extractor: ExtractorPort,
        retrieval: Any | None = None,
    ) -> None:
        self._ontology = ontology
        self._knowledge = knowledge
        self._graph = graph
        self._evidence = evidence
        self._extractor = extractor
        self._retrieval = retrieval

    @property
    def ontology(self) -> OntologyPort:
        return self._ontology

    def _exact_spo_covered(self, history: list[Claim], obj: str) -> bool:
        for claim in history:
            if claim.object == obj:
                return True
            if claim.status in ("active", "staging") and join_claim_objects(claim.object, obj) == claim.object:
                return True
        return False

    def _fold_complementary_into_actives(
        self,
        *,
        family_id: str,
        history: list[Claim],
        subject: str,
        predicate: str,
        obj: str,
        subject_type: str,
        object_type: str,
        confidence: float,
        source_id: str,
        quote: str,
        quote_start: int,
        quote_end: int,
    ) -> Claim:
        """Supersede active peers and write one active claim with joined objects."""
        actives = [claim for claim in history if claim.status == "active"]
        merged_obj = join_claim_objects(*([claim.object for claim in actives] + [obj]))

        now = datetime.now(timezone.utc)
        source_ids: list[str] = []
        for peer in actives:
            for sid in peer.source_ids:
                if sid not in source_ids:
                    source_ids.append(sid)
            self._knowledge.mark_superseded(peer.id, valid_to=now)
            if self._retrieval is not None and hasattr(self._retrieval, "remove_claim"):
                self._retrieval.remove_claim(peer.id)
        if source_id not in source_ids:
            source_ids.append(source_id)

        claim_id = str(uuid.uuid4())
        claim = Claim(
            id=claim_id,
            family_id=family_id,
            version=max((item.version for item in history), default=0) + 1,
            subject=subject,
            predicate=predicate,
            object=merged_obj,
            subject_type=subject_type,
            object_type=object_type,
            confidence=max([confidence] + [peer.confidence for peer in actives]),
            status="active",
            valid_from=now,
            valid_to=None,
            source_ids=source_ids,
        )
        self._knowledge.append_claim(claim)

        subject_entity = _entity_id(subject, subject_type)
        object_entity = _entity_id(merged_obj, object_type)
        self._graph.upsert_entity(subject_entity, subject_type, {"name": subject})
        self._graph.upsert_entity(object_entity, object_type, {"name": merged_obj})
        self._graph.upsert_relation(subject_entity, predicate, object_entity, {})
        self._evidence.bind(
            claim_id,
            source_id,
            TextSpan(source_id, quote_start, quote_end, quote),
            confidence,
        )
        if self._retrieval is not None:
            self._retrieval.index_claim(claim)
        return claim

    def ingest(
        self,
        source_id: str,
        staging: bool = False,
        *,
        llm_client: Any | None = None,
        domain: Any | None = None,
        settings: Any | None = None,
    ) -> CompileReport:
        text = self._knowledge.get_source_text(source_id)
        if text is None:
            return CompileReport(
                source_id=source_id,
                claims_created=0,
                entities_upserted=0,
                evidence_links=0,
                quarantined=0,
                errors=["source text not found"],
            )

        from infra.settings import Settings, get_settings

        resolved_settings = settings or get_settings()
        source = self._knowledge.get_source(source_id)
        stored_chunks = self._knowledge.list_chunks(source_id, status="active")
        candidates = select_hybrid_candidates(
            text,
            rule_extractor=self._extractor,
            llm_client=llm_client,
            domain=domain,
            settings=resolved_settings,
            ontology=self._ontology,
            title=getattr(source, "title", None) if source else None,
            source_chunks=stored_chunks or None,
        )
        candidates = merge_complementary_extracted(candidates)

        claims_created = 0
        entities_upserted = 0
        evidence_links = 0
        quarantined = 0
        errors: list[str] = []

        for extracted in candidates:
            subject = self._ontology.normalize_term(extracted.subject)
            obj = self._ontology.normalize_term(extracted.object)
            subject_type = self._ontology.resolve_entity_type(subject) or "Concept"
            object_type = self._ontology.resolve_entity_type(obj) or "Concept"

            if not self._ontology.validate_claim(subject_type, extracted.predicate, object_type):
                self._knowledge.add_quarantine(
                    "invalid_predicate",
                    {
                        "subject": subject,
                        "predicate": extracted.predicate,
                        "object": obj,
                        "subject_type": subject_type,
                        "object_type": object_type,
                    },
                )
                quarantined += 1
                continue

            family_id = _family_id(subject, extracted.predicate, object_type)
            history = self._knowledge.get_claim_history(family_id)
            if self._exact_spo_covered(history, obj):
                continue

            actives = [claim for claim in history if claim.status == "active"]
            if actives and not is_exclusive_predicate(extracted.predicate):
                merged_obj = join_claim_objects(*([claim.object for claim in actives] + [obj]))
                if len(actives) == 1 and merged_obj == actives[0].object:
                    continue
                self._fold_complementary_into_actives(
                    family_id=family_id,
                    history=history,
                    subject=subject,
                    predicate=extracted.predicate,
                    obj=obj,
                    subject_type=subject_type,
                    object_type=object_type,
                    confidence=extracted.confidence,
                    source_id=source_id,
                    quote=extracted.quote,
                    quote_start=extracted.start,
                    quote_end=extracted.end,
                )
                claims_created += 1
                entities_upserted += 2
                evidence_links += 1
                continue

            claim_id = str(uuid.uuid4())
            has_active_conflict = any(claim.status == "active" and claim.object != obj for claim in history)
            claim_status = "staging" if staging or has_active_conflict else "active"
            claim = Claim(
                id=claim_id,
                family_id=family_id,
                version=max((item.version for item in history), default=0) + 1,
                subject=subject,
                predicate=extracted.predicate,
                object=obj,
                subject_type=subject_type,
                object_type=object_type,
                confidence=extracted.confidence,
                status=claim_status,
                valid_from=datetime.now(timezone.utc),
                valid_to=None,
                source_ids=[source_id],
            )
            self._knowledge.append_claim(claim)
            claims_created += 1

            subject_entity = _entity_id(subject, subject_type)
            object_entity = _entity_id(obj, object_type)
            self._graph.upsert_entity(subject_entity, subject_type, {"name": subject})
            self._graph.upsert_entity(object_entity, object_type, {"name": obj})
            entities_upserted += 2
            self._graph.upsert_relation(subject_entity, extracted.predicate, object_entity, {})

            self._evidence.bind(
                claim_id,
                source_id,
                TextSpan(source_id, extracted.start, extracted.end, extracted.quote),
                extracted.confidence,
            )
            evidence_links += 1

            if self._retrieval is not None and claim_status == "active":
                self._retrieval.index_claim(claim)

        return CompileReport(
            source_id=source_id,
            claims_created=claims_created,
            entities_upserted=entities_upserted,
            evidence_links=evidence_links,
            quarantined=quarantined,
            errors=errors,
        )

    def apply_extracted_claims(
        self,
        source_id: str,
        extracted: list[ExtractedClaim],
        *,
        staging: bool = False,
        min_confidence: float = 0.5,
        existing_skip: bool = True,
        open_predicates: bool = False,
    ) -> CompileReport:
        text = self._knowledge.get_source_text(source_id)
        if text is None:
            return CompileReport(
                source_id=source_id,
                claims_created=0,
                entities_upserted=0,
                evidence_links=0,
                quarantined=0,
                errors=["source text not found"],
            )

        claims_created = 0
        entities_upserted = 0
        evidence_links = 0
        quarantined = 0

        # Quarantine low-confidence first so complementary merge cannot
        # absorb them via confidence=max(...) and skip low_confidence isolation.
        kept: list[ExtractedClaim] = []
        for candidate in extracted:
            if candidate.confidence < min_confidence:
                self._knowledge.add_quarantine(
                    "low_confidence",
                    {
                        "subject": candidate.subject,
                        "predicate": candidate.predicate,
                        "object": candidate.object,
                        "confidence": candidate.confidence,
                        "quote": candidate.quote,
                        "start": candidate.start,
                        "end": candidate.end,
                        "source_id": source_id,
                    },
                )
                quarantined += 1
            else:
                kept.append(candidate)

        extracted = merge_complementary_extracted(kept)

        for candidate in extracted:
            raw = {
                "subject": candidate.subject,
                "predicate": candidate.predicate,
                "object": candidate.object,
                "confidence": candidate.confidence,
                "quote": candidate.quote,
                "start": candidate.start,
                "end": candidate.end,
                "source_id": source_id,
            }
            if candidate.confidence < min_confidence:
                self._knowledge.add_quarantine("low_confidence", raw)
                quarantined += 1
                continue

            quote_start = text.find(candidate.quote)
            if not candidate.quote or quote_start < 0:
                self._knowledge.add_quarantine("span_missing", raw)
                quarantined += 1
                continue

            subject = self._ontology.normalize_term(candidate.subject)
            obj = self._ontology.normalize_term(candidate.object)
            subject_type = self._ontology.resolve_entity_type(subject) or "Concept"
            object_type = self._ontology.resolve_entity_type(obj) or "Concept"
            raw.update(
                {
                    "subject": subject,
                    "object": obj,
                    "subject_type": subject_type,
                    "object_type": object_type,
                }
            )
            if not self._ontology.validate_claim(subject_type, candidate.predicate, object_type):
                if open_predicates:
                    self._ontology.register_predicate(subject_type, candidate.predicate, object_type)
                else:
                    self._knowledge.add_quarantine("invalid_predicate", raw)
                    quarantined += 1
                    continue

            family_id = _family_id(subject, candidate.predicate, object_type)
            history = self._knowledge.get_claim_history(family_id)
            if existing_skip and self._exact_spo_covered(history, obj):
                continue

            actives = [claim for claim in history if claim.status == "active"]
            if actives and not is_exclusive_predicate(candidate.predicate):
                merged_obj = join_claim_objects(*([claim.object for claim in actives] + [obj]))
                if len(actives) == 1 and merged_obj == actives[0].object:
                    continue
                self._fold_complementary_into_actives(
                    family_id=family_id,
                    history=history,
                    subject=subject,
                    predicate=candidate.predicate,
                    obj=obj,
                    subject_type=subject_type,
                    object_type=object_type,
                    confidence=candidate.confidence,
                    source_id=source_id,
                    quote=candidate.quote,
                    quote_start=quote_start,
                    quote_end=quote_start + len(candidate.quote),
                )
                claims_created += 1
                entities_upserted += 2
                evidence_links += 1
                continue

            has_active_conflict = any(claim.status == "active" and claim.object != obj for claim in history)
            claim_status = "staging" if staging or has_active_conflict else "active"
            claim_id = str(uuid.uuid4())
            claim = Claim(
                id=claim_id,
                family_id=family_id,
                version=max((item.version for item in history), default=0) + 1,
                subject=subject,
                predicate=candidate.predicate,
                object=obj,
                subject_type=subject_type,
                object_type=object_type,
                confidence=candidate.confidence,
                status=claim_status,
                valid_from=datetime.now(timezone.utc),
                valid_to=None,
                source_ids=[source_id],
            )
            self._knowledge.append_claim(claim)
            claims_created += 1

            subject_entity = _entity_id(subject, subject_type)
            object_entity = _entity_id(obj, object_type)
            self._graph.upsert_entity(subject_entity, subject_type, {"name": subject})
            self._graph.upsert_entity(object_entity, object_type, {"name": obj})
            entities_upserted += 2
            self._graph.upsert_relation(subject_entity, candidate.predicate, object_entity, {})

            quote_end = quote_start + len(candidate.quote)
            self._evidence.bind(
                claim_id,
                source_id,
                TextSpan(source_id, quote_start, quote_end, candidate.quote),
                candidate.confidence,
            )
            evidence_links += 1

            if self._retrieval is not None and claim_status == "active":
                self._retrieval.index_claim(claim)

        return CompileReport(
            source_id=source_id,
            claims_created=claims_created,
            entities_upserted=entities_upserted,
            evidence_links=evidence_links,
            quarantined=quarantined,
            errors=[],
        )
