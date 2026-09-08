import { apiFetch } from "./http";
import type { SourceItem, UploadSourceResponse } from "./types";

type BackendSource = {
  id: string;
  title: string;
  type: string;
  uri: string;
  version: string;
  created_at: string;
  status: string;
};

function mapSource(raw: BackendSource): SourceItem {
  return {
    id: raw.id,
    filename: raw.title,
    created_at: raw.created_at,
    compile_status: raw.status as SourceItem["compile_status"],
  };
}

export async function listSources(kbId: string): Promise<SourceItem[]> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources`);
  const raw = (await response.json()) as BackendSource[];
  return raw.map(mapSource);
}

export async function uploadSource(kbId: string, file: File): Promise<UploadSourceResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/upload`, {
    method: "POST",
    body: formData,
  });
  return response.json() as Promise<UploadSourceResponse>;
}
