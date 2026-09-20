import { apiFetch } from "./http";
import type {
  GraphEdge,
  GraphEntity,
  GraphNeighborsResponse,
  GraphRetrieveResponse,
  GraphSnapshotResponse,
} from "./types";

export type GraphEntitySearchOptions = {
  q?: string;
  predicate?: string;
};

export async function fetchGraphSnapshot(
  kbId: string,
  options?: { entityLimit?: number; edgeLimit?: number },
): Promise<GraphSnapshotResponse> {
  const params = new URLSearchParams();
  params.set("entity_limit", String(options?.entityLimit ?? 200));
  params.set("edge_limit", String(options?.edgeLimit ?? 500));
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/graph/snapshot?${params.toString()}`);
  return (await response.json()) as GraphSnapshotResponse;
}

export async function listGraphEntities(kbId: string, options?: GraphEntitySearchOptions): Promise<GraphEntity[]> {
  const params = new URLSearchParams();
  if (options?.q?.trim()) {
    params.set("q", options.q.trim());
  }
  if (options?.predicate?.trim()) {
    params.set("predicate", options.predicate.trim());
  }
  const query = params.toString();
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/graph/entities${query ? `?${query}` : ""}`);
  return (await response.json()) as GraphEntity[];
}

export async function listGraphPredicates(kbId: string, q?: string): Promise<string[]> {
  const params = new URLSearchParams();
  if (q?.trim()) {
    params.set("q", q.trim());
  }
  const query = params.toString();
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/graph/predicates${query ? `?${query}` : ""}`);
  return (await response.json()) as string[];
}

export async function fetchGraphNeighbors(
  kbId: string,
  entityId: string,
  options?: { predicates?: string[] },
): Promise<GraphNeighborsResponse> {
  const params = new URLSearchParams();
  for (const predicate of options?.predicates ?? []) {
    if (predicate.trim()) {
      params.append("predicates", predicate.trim());
    }
  }
  const query = params.toString();
  const response = await apiFetch(
    `/admin/knowledge-bases/${kbId}/graph/entities/${encodeURIComponent(entityId)}/neighbors${query ? `?${query}` : ""}`,
  );
  return (await response.json()) as GraphNeighborsResponse;
}

export async function retrieveGraph(
  kbId: string,
  query: string,
  options?: { topK?: number },
): Promise<GraphRetrieveResponse> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/graph/retrieve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      top_k: options?.topK ?? 20,
    }),
  });
  return (await response.json()) as GraphRetrieveResponse;
}

export type { GraphEdge, GraphEntity, GraphNeighborsResponse, GraphRetrieveResponse, GraphSnapshotResponse };
