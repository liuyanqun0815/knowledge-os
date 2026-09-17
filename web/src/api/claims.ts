import { apiFetch } from "./http";
import type { ClaimHistoryItem, ClaimListItem } from "./types";

export type ListClaimsFilters = {
  status?: string;
  subject?: string;
  predicate?: string;
  object?: string;
};

export async function listClaims(kbId: string, filters: ListClaimsFilters = {}): Promise<ClaimListItem[]> {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.subject) {
    params.set("subject", filters.subject);
  }
  if (filters.predicate) {
    params.set("predicate", filters.predicate);
  }
  if (filters.object) {
    params.set("object", filters.object);
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

export async function approveStagingClaim(kbId: string, claimId: string): Promise<ClaimListItem> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/claims/${claimId}/approve-staging`, {
    method: "POST",
  });
  return response.json() as Promise<ClaimListItem>;
}

export async function rejectStagingClaim(kbId: string, claimId: string): Promise<{ claim: ClaimListItem }> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/claims/${claimId}/reject-staging`, {
    method: "POST",
  });
  return response.json() as Promise<{ claim: ClaimListItem }>;
}
