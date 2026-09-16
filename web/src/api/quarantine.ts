import { apiFetch } from "./http";
import type { ClaimListItem, QuarantineItem } from "./types";

export type ApproveQuarantineResponse = {
  claim: ClaimListItem;
};

export type ApproveAllQuarantineFailure = {
  id: number;
  detail: string;
};

export type ApproveAllQuarantineResponse = {
  approved_count: number;
  failed_count: number;
  claims: ClaimListItem[];
  failures: ApproveAllQuarantineFailure[];
};

export async function listQuarantine(kbId: string): Promise<QuarantineItem[]> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/quarantine`);
  return response.json() as Promise<QuarantineItem[]>;
}

export async function approveQuarantine(kbId: string, quarantineId: number): Promise<ApproveQuarantineResponse> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/quarantine/${quarantineId}/approve`, {
    method: "POST",
  });
  return response.json() as Promise<ApproveQuarantineResponse>;
}

export async function approveAllQuarantine(kbId: string): Promise<ApproveAllQuarantineResponse> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/quarantine/approve-all`, {
    method: "POST",
  });
  return response.json() as Promise<ApproveAllQuarantineResponse>;
}
