from akos.domain.ports.evidence import EvidencePort
from akos.domain.ports.knowledge import KnowledgePort
from akos.domain.ports.verification import VerificationResult
from verification.service import VerificationService


def verify_claims(
    service: VerificationService,
    knowledge: KnowledgePort,
    evidence: EvidencePort,
    claim_ids: list[str],
) -> VerificationResult:
    return service.verify_claims(knowledge, evidence, claim_ids)
