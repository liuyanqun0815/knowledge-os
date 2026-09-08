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
};

export type UploadSourceResponse = {
  source_id: string;
  path: string;
  claims_created: number;
  entities_upserted: number;
  evidence_links: number;
  quarantined: number;
  errors: string[];
};

export type AgentTraceStep = {
  node: string;
  status: "ok" | "error" | "skipped";
  duration_ms?: number;
  summary?: string;
  detail?: unknown;
};

export type AskResponse = {
  text: string;
  claim_ids: string[];
  evidence: Record<string, unknown>[];
  confidence: number;
  retrieval_mode: string;
  request_id?: string | null;
  trace?: AgentTraceStep[] | null;
};
