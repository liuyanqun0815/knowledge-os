import { apiFetch } from "./http";
import type { ClaimListItem, QuarantineItem } from "./types";

export type ApproveQuarantineResponse = {
  claim: ClaimListItem;
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
