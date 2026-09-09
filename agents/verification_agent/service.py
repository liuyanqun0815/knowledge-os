from evidence.ports import EvidencePort
from knowledge.ports import KnowledgePort
from verification.ports import VerificationResult
from verification.service import VerificationService


def verify_claims(
    service: VerificationService,
    knowledge: KnowledgePort,
    evidence: EvidencePort,
    claim_ids: list[str],
) -> VerificationResult:
    return service.verify_claims(knowledge, evidence, claim_ids)
