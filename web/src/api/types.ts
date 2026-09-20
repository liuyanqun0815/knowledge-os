export type KnowledgeBase = {
  id: string;
  name: string;
  domain_type: string;
  description: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};

export type SourceItem = {
  id: string;
  filename: string;
  created_at: string;
  compile_status:
    | "pending"
    | "running"
    | "enriching"
    | "succeeded"
    | "succeeded_partial"
    | "failed"
    | "ready";
  error_summary?: string | null;
  relative_path?: string;
  directory?: string;
  claims_count?: number;
};

export type UploadSourceResultItem = {
  source_id: string;
  path: string;
  claims_created: number;
  entities_upserted: number;
  evidence_links: number;
  quarantined: number;
  errors: string[];
  relative_path?: string;
  directory?: string;
};

export type SourceUploadResponse = {
  upload_mode: "single" | "zip" | "tree";
  files_total: number;
  files_ingested: number;
  files_skipped: number;
  results: UploadSourceResultItem[];
  errors: string[];
  accepted_async?: boolean;
  ingest_summary?: string | null;
};

/** @deprecated use UploadSourceResultItem */
export type UploadSourceResponse = UploadSourceResultItem;

/** @deprecated use SourceUploadResponse */
export type ZipUploadResponse = SourceUploadResponse;

export type UploadSourceOptions = {
  replacesSourceId?: string;
  relativePath?: string;
  /** auto | on | off — bind generic subjects (本产品/投资者…) to document product anchor */
  subjectBindMode?: "auto" | "on" | "off";
};

export type SourceContent = {
  source_id: string;
  title: string;
  relative_path: string;
  content: string;
  size_bytes: number;
  encoding: string;
};

export type SourceChunkItem = {
  id: string;
  source_id: string;
  chunk_index: number;
  title: string | null;
  summary: string | null;
  text: string;
  start: number;
  end: number;
  section_path: string[];
  topics: string[];
  token_count: number;
  status: string;
  content_hash: string;
  created_at: string | null;
};

export type TraceChunkHit = {
  hit_type?: string;
  chunk_id?: string;
  claim_id?: string;
  source_id?: string;
  ref_id?: string;
  path?: string;
  chunk_index?: number;
  title?: string | null;
  score?: number;
  snippet?: string;
};

export type TraceChunkItem = {
  chunk_id: string;
  source_id?: string;
  chunk_index?: number;
  title?: string | null;
  excerpt?: string;
  status?: string;
};

export type AgentTraceStep = {
  node: string;
  status: "ok" | "error" | "skipped";
  duration_ms?: number;
  summary?: string;
  detail?: unknown;
};

export type ClaimHistoryItem = {
  id: string;
  family_id: string;
  version: number;
  subject: string;
  predicate: string;
  object: string;
  status: string;
  valid_from: string | null;
  valid_to: string | null;
  source_ids: string[];
};

export type ClaimListItem = ClaimHistoryItem & {
  subject_type: string;
  object_type: string;
  confidence: number;
};

export type QuarantineItem = {
  id: number;
  reason: string;
  raw: Record<string, unknown>;
};

export type EvolveSourceResponse = {
  source_old_id: string;
  source_new_id: string;
  claims_activated: string[];
  claims_superseded: string[];
  events_created: string[];
  errors: string[];
};

export type AskResponse = {
  text: string;
  claim_ids: string[];
  evidence: Record<string, unknown>[];
  confidence: number;
  retrieval_mode: string;
  verification_status: string;
  competing_claim_ids: string[];
  procedure_id?: string | null;
  as_of?: string | null;
  request_id?: string | null;
  duration_ms?: number | null;
  trace?: AgentTraceStep[] | null;
};

export type GraphEntity = {
  id: string;
  type: string;
  name: string;
};

export type GraphEdge = {
  src: string;
  predicate: string;
  dst: string;
  src_name: string;
  dst_name: string;
};

export type GraphSnapshotResponse = {
  entities: GraphEntity[];
  edges: GraphEdge[];
  truncated: boolean;
  entity_total: number;
};

export type GraphNeighborsResponse = {
  entity_id: string;
  entities: GraphEntity[];
  edges: GraphEdge[];
};

export type GraphRetrieveHit = {
  score: number;
  snippet: string | null;
  claim_id: string | null;
  entity_id: string | null;
  src?: string | null;
  dst?: string | null;
  predicate?: string | null;
};

export type GraphRetrieveResponse = {
  query: string;
  hit_count: number;
  hits: GraphRetrieveHit[];
  entities: GraphEntity[];
  edges: GraphEdge[];
};
