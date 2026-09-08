from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from knowledge_base.models import KnowledgeBase


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    domain_type: str
    description: str = ""


class PatchKnowledgeBaseRequest(BaseModel):
    name: str | None = None
    domain_type: str | None = None
    description: str | None = None
    status: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    domain_type: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, kb: KnowledgeBase) -> KnowledgeBaseResponse:
        return cls(
            id=kb.id,
            name=kb.name,
            domain_type=kb.domain_type,
            description=kb.description,
            status=kb.status,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )


class SourceResponse(BaseModel):
    id: str
    title: str
    type: str
    uri: str
    version: str
    created_at: datetime
    status: str


class UploadSourceResponse(BaseModel):
    source_id: str
    path: str
    claims_created: int
    entities_upserted: int
    evidence_links: int
    quarantined: int
    errors: list[str] = Field(default_factory=list)
