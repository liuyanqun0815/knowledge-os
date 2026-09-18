from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from akos.domain.ports.evolution import ApplyReport
from knowledge.models import Claim
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
    relative_path: str = ""
    directory: str = "/"
    claims_count: int = 0
    enrichment_status: str | None = None


class UploadSourceResponse(BaseModel):
    source_id: str
    path: str
    claims_created: int
    entities_upserted: int
    evidence_links: int
    quarantined: int
    errors: list[str] = Field(default_factory=list)


class ZipUploadItemResponse(UploadSourceResponse):
    relative_path: str = ""
    directory: str = "/"


class SourceUploadResponse(BaseModel):
    upload_mode: str
    files_total: int
    files_ingested: int
    files_skipped: int
    results: list[ZipUploadItemResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    ingest_summary: str | None = None
    accepted_async: bool = False


class MoveSourcesRequest(BaseModel):
    from_path: str
    to_path: str


class DeleteTreeRequest(BaseModel):
    path: str


class DeleteTreeResponse(BaseModel):
    deleted_count: int


class SourceContentResponse(BaseModel):
    source_id: str
    title: str
    relative_path: str
    content: str
    size_bytes: int
    encoding: str = "utf-8"


class ZipUploadResponse(SourceUploadResponse):
    """Backward-compatible alias for batch upload responses."""


class EvolveSourceRequest(BaseModel):
    replaces_source_id: str | None = None


class EvolveSourceResponse(BaseModel):
    source_old_id: str
    source_new_id: str
    claims_activated: list[str] = Field(default_factory=list)
    claims_superseded: list[str] = Field(default_factory=list)
    events_created: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def from_report(cls, report: ApplyReport) -> EvolveSourceResponse:
        return cls(
            source_old_id=report.source_old_id,
            source_new_id=report.source_new_id,
            claims_activated=list(report.claims_activated),
            claims_superseded=list(report.claims_superseded),
            events_created=list(report.events_created),
            errors=list(report.errors),
        )


class ClaimHistoryItemResponse(BaseModel):
    id: str
    family_id: str
    version: int
    subject: str
    predicate: str
    object: str
    status: str
    valid_from: datetime | None
    valid_to: datetime | None
    source_ids: list[str] = Field(default_factory=list)

    @classmethod
    def from_claim(cls, claim: Claim) -> ClaimHistoryItemResponse:
        return cls(
            id=claim.id,
            family_id=claim.family_id,
            version=claim.version,
            subject=claim.subject,
            predicate=claim.predicate,
            object=claim.object,
            status=claim.status,
            valid_from=claim.valid_from,
            valid_to=claim.valid_to,
            source_ids=list(claim.source_ids),
        )


class ClaimListItemResponse(ClaimHistoryItemResponse):
    subject_type: str
    object_type: str
    confidence: float

    @classmethod
    def from_claim(cls, claim: Claim) -> ClaimListItemResponse:
        return cls(
            id=claim.id,
            family_id=claim.family_id,
            version=claim.version,
            subject=claim.subject,
            predicate=claim.predicate,
            object=claim.object,
            status=claim.status,
            valid_from=claim.valid_from,
            valid_to=claim.valid_to,
            source_ids=list(claim.source_ids),
            subject_type=claim.subject_type,
            object_type=claim.object_type,
            confidence=claim.confidence,
        )


class SourceChunkResponse(BaseModel):
    id: str
    source_id: str
    chunk_index: int
    title: str | None = None
    summary: str | None = None
    text: str
    start: int
    end: int
    section_path: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    token_count: int = 0
    status: str = "active"
    content_hash: str = ""
    created_at: datetime | None = None

    @classmethod
    def from_chunk(cls, chunk) -> SourceChunkResponse:
        return cls(
            id=chunk.id,
            source_id=chunk.source_id,
            chunk_index=chunk.chunk_index,
            title=chunk.title,
            summary=chunk.summary,
            text=chunk.text,
            start=chunk.start,
            end=chunk.end,
            section_path=list(chunk.section_path),
            topics=list(chunk.topics),
            token_count=chunk.token_count,
            status=chunk.status,
            content_hash=chunk.content_hash,
            created_at=chunk.created_at,
        )


class QuarantineItemResponse(BaseModel):
    id: int
    reason: str
    raw: dict


class ApproveQuarantineResponse(BaseModel):
    claim: ClaimListItemResponse


class RejectStagingClaimResponse(BaseModel):
    claim: ClaimListItemResponse


class ApproveAllQuarantineFailure(BaseModel):
    id: int
    detail: str


class ApproveAllQuarantineResponse(BaseModel):
    approved_count: int
    failed_count: int
    claims: list[ClaimListItemResponse] = Field(default_factory=list)
    failures: list[ApproveAllQuarantineFailure] = Field(default_factory=list)


class LintIssueResponse(BaseModel):
    code: str
    severity: str
    message: str
    refs: dict[str, str] = Field(default_factory=dict)


class LintReportResponse(BaseModel):
    kb_id: str
    checked_at: datetime
    issues: list[LintIssueResponse] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class WikiExportRequest(BaseModel):
    output_dir: str | None = None
    use_llm: bool = False


class WikiExportResponse(BaseModel):
    kb_id: str
    output_path: str
    files_written: int
    source_pages: int
    entity_pages: int
    topic_pages: int = 0
    exported_at: datetime


class WikiCompileResponse(BaseModel):
    kb_id: str
    wiki_root: str
    pages_written: int
    topics: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class WikiTreePageItem(BaseModel):
    page_id: str
    title: str
    summary: str | None = None


class WikiTreeHubItem(BaseModel):
    name: str
    description: str | None = None
    pages: list[WikiTreePageItem] = Field(default_factory=list)


class WikiTreeResponse(BaseModel):
    kb_id: str
    wiki_root: str
    hubs: list[WikiTreeHubItem] = Field(default_factory=list)


class WikiPageResponse(BaseModel):
    page_id: str
    title: str
    path: str
    markdown: str


class WikiSearchHit(BaseModel):
    page_id: str
    title: str
    snippets: list[str] = Field(default_factory=list)


class WikiSearchResponse(BaseModel):
    query: str
    total: int
    hits: list[WikiSearchHit] = Field(default_factory=list)


class PurgeStaleChunksResponse(BaseModel):
    kb_id: str
    deleted: int
    sources_purged: int = 0


class TopicRebuildResponse(BaseModel):
    topics_created: int
    topics_updated: int
    topics_stale: int
    edges: int


class DebugAskRequest(BaseModel):
    question: str
    session_id: str | None = None
    as_of: datetime | None = None


class DebugAskResponse(BaseModel):
    text: str
    claim_ids: list[str]
    evidence: list[dict]
    confidence: float
    retrieval_mode: str
    verification_status: str = "verified"
    competing_claim_ids: list[str] = Field(default_factory=list)
    procedure_id: str | None = None
    as_of: datetime | None = None
    trace: list[dict] = Field(default_factory=list)
    duration_ms: int | None = None


class GraphNeighborResponse(BaseModel):
    src: str
    predicate: str
    dst: str
    props: dict = Field(default_factory=dict)


class GraphEntityResponse(BaseModel):
    id: str
    type: str
    name: str


class GraphEdgeResponse(BaseModel):
    src: str
    predicate: str
    dst: str
    src_name: str
    dst_name: str


class GraphSnapshotResponse(BaseModel):
    entities: list[GraphEntityResponse] = Field(default_factory=list)
    edges: list[GraphEdgeResponse] = Field(default_factory=list)
    truncated: bool = False
    entity_total: int = 0


class GraphNeighborsResponse(BaseModel):
    entity_id: str
    entities: list[GraphEntityResponse] = Field(default_factory=list)
    edges: list[GraphEdgeResponse] = Field(default_factory=list)
