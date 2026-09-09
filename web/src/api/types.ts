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
  compile_status: "pending" | "running" | "succeeded" | "failed";
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
  upload_mode: "single" | "zip";
  files_total: number;
  files_ingested: number;
  files_skipped: number;
  results: UploadSourceResultItem[];
  errors: string[];
};

/** @deprecated use UploadSourceResultItem */
export type UploadSourceResponse = UploadSourceResultItem;

/** @deprecated use SourceUploadResponse */
export type ZipUploadResponse = SourceUploadResponse;

export type UploadSourceOptions = {
  replacesSourceId?: string;
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
  trace?: AgentTraceStep[] | null;
};
