import { apiFetch } from "./http";
import type { GraphEdge, GraphEntity, GraphNeighborsResponse, GraphSnapshotResponse } from "./types";

export type GraphEntitySearchOptions = {
  q?: string;
  predicate?: string;
};

export async function fetchGraphSnapshot(
  kbId: string,
  options?: { entityLimit?: number; edgeLimit?: number },
): Promise<GraphSnapshotResponse> {
  const params = new URLSearchParams();
  if (options?.entityLimit) {
    params.set("entity_limit", String(options.entityLimit));
  }
  if (options?.edgeLimit) {
    params.set("edge_limit", String(options.edgeLimit));
  }
  const query = params.toString();
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/graph/snapshot${query ? `?${query}` : ""}`);
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

export type { GraphEdge, GraphEntity, GraphNeighborsResponse, GraphSnapshotResponse };
