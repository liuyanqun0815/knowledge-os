from dataclasses import dataclass, field


@dataclass
class VerificationResult:
    verification_status: str
    verified_claim_ids: list[str] = field(default_factory=list)
    unverified_claim_ids: list[str] = field(default_factory=list)
    competing_claim_ids: list[str] = field(default_factory=list)
    adjusted_confidence: float = 0.0
