import { apiFetch } from "./http";
import type { EvolveSourceResponse } from "./types";

export type EvolveSourceOptions = {
  replacesSourceId?: string;
};

export async function evolveSource(
  kbId: string,
  sourceId: string,
  options: EvolveSourceOptions = {},
): Promise<EvolveSourceResponse> {
  const body: Record<string, string> = {};
  if (options.replacesSourceId) {
    body.replaces_source_id = options.replacesSourceId;
  }

  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${sourceId}/evolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<EvolveSourceResponse>;
}
