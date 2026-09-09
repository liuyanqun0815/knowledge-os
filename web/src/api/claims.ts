import { apiFetch } from "./http";
import type { ClaimHistoryItem, ClaimListItem } from "./types";

export type ListClaimsFilters = {
  status?: string;
  subject?: string;
};

export async function listClaims(kbId: string, filters: ListClaimsFilters = {}): Promise<ClaimListItem[]> {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.subject) {
    params.set("subject", filters.subject);
  }
  const query = params.toString();
  const path = `/admin/knowledge-bases/${kbId}/claims${query ? `?${query}` : ""}`;
  const response = await apiFetch(path);
  return response.json() as Promise<ClaimListItem[]>;
}

export async function fetchClaimHistory(kbId: string, familyId: string): Promise<ClaimHistoryItem[]> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/claims/${familyId}/history`);
  return response.json() as Promise<ClaimHistoryItem[]>;
}
