from akos.domain.ports.evidence import EvidencePort
from akos.domain.ports.knowledge import KnowledgePort
from akos.domain.ports.verification import VerificationResult


class VerificationService:
    def verify_claims(
        self,
        knowledge: KnowledgePort,
        evidence: EvidencePort,
        claim_ids: list[str],
    ) -> VerificationResult:
        verified_claim_ids: list[str] = []
        unverified_claim_ids: list[str] = []
        competing_claim_ids: list[str] = []

        for claim_id in claim_ids:
            if self._claim_spans_verified(knowledge, evidence, claim_id):
                verified_claim_ids.append(claim_id)
            else:
                unverified_claim_ids.append(claim_id)

        seen_families: set[str] = set()
        for claim_id in claim_ids:
            claim = knowledge.get_claim(claim_id)
            if claim is None or claim.family_id in seen_families:
                continue
            seen_families.add(claim.family_id)
            active_in_family = [
                candidate
                for candidate in knowledge.get_claim_history(claim.family_id)
                if candidate.status == "active"
            ]
            if len(active_in_family) > 1:
                for active_claim in active_in_family:
                    if active_claim.id not in competing_claim_ids:
                        competing_claim_ids.append(active_claim.id)

        verification_status = self._resolve_status(
            verified_claim_ids,
            unverified_claim_ids,
            competing_claim_ids,
        )

        base_confidence = evidence.explain(claim_ids).confidence
        adjusted_confidence = base_confidence * 0.5 if unverified_claim_ids else base_confidence

        return VerificationResult(
            verification_status=verification_status,
            verified_claim_ids=verified_claim_ids,
            unverified_claim_ids=unverified_claim_ids,
            competing_claim_ids=competing_claim_ids,
            adjusted_confidence=adjusted_confidence,
        )

    def _claim_spans_verified(self, knowledge: KnowledgePort, evidence: EvidencePort, claim_id: str) -> bool:
        bundle = evidence.explain([claim_id])
        if not bundle.items:
            return False
        for item in bundle.items:
            source_text = knowledge.get_source_text(item["source_id"])
            if source_text is None or item["quote"] not in source_text:
                return False
        return True

    def _resolve_status(
        self,
        verified_claim_ids: list[str],
        unverified_claim_ids: list[str],
        competing_claim_ids: list[str],
    ) -> str:
        if competing_claim_ids:
            return "conflict"
        if verified_claim_ids and not unverified_claim_ids:
            return "verified"
        if unverified_claim_ids and not verified_claim_ids:
            return "unverified"
        if verified_claim_ids and unverified_claim_ids:
            return "partial"
        return "verified"
