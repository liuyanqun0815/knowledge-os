from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING, Any

from compiler.ports import CompileReport, ExtractedClaim, ExtractorPort
from compiler.intersect import select_hybrid_candidates
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
        candidates = select_hybrid_candidates(
            text,
            rule_extractor=self._extractor,
            llm_client=llm_client,
            domain=domain,
            settings=resolved_settings,
            ontology=self._ontology,
            title=getattr(source, "title", None) if source else None,
        )

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

            claim_id = str(uuid.uuid4())
            claim_status = "staging" if staging else "active"
            claim = Claim(
                id=claim_id,
                family_id=_family_id(subject, extracted.predicate, object_type),
                version=1,
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

            if self._retrieval is not None and not staging:
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
            if existing_skip and any(claim.object == obj for claim in history):
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
