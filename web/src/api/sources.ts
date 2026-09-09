import { apiFetch } from "./http";
import type { ClaimListItem, SourceItem, SourceUploadResponse, UploadSourceOptions } from "./types";

type BackendSource = {
  id: string;
  title: string;
  type: string;
  uri: string;
  version: string;
  created_at: string;
  status: string;
  relative_path?: string;
  directory?: string;
  claims_count?: number;
};

function mapSource(raw: BackendSource): SourceItem {
  return {
    id: raw.id,
    filename: raw.title,
    created_at: raw.created_at,
    compile_status: raw.status as SourceItem["compile_status"],
    relative_path: raw.relative_path,
    directory: raw.directory,
    claims_count: raw.claims_count,
  };
}

export type ListSourcesOptions = {
  query?: string;
};

export async function listSources(kbId: string, options: ListSourcesOptions = {}): Promise<SourceItem[]> {
  const params = new URLSearchParams();
  if (options.query?.trim()) {
    params.set("q", options.query.trim());
  }
  const query = params.toString();
  const path = `/admin/knowledge-bases/${kbId}/sources${query ? `?${query}` : ""}`;
  const response = await apiFetch(path);
  const raw = (await response.json()) as BackendSource[];
  return raw.map(mapSource);
}

export type { UploadSourceOptions };

export async function uploadSource(
  kbId: string,
  file: File,
  options: UploadSourceOptions = {},
): Promise<SourceUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (options.replacesSourceId) {
    formData.append("replaces_source_id", options.replacesSourceId);
  }

  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/upload`, {
    method: "POST",
    body: formData,
  });
  return response.json() as Promise<SourceUploadResponse>;
}

export async function fetchSourceClaims(kbId: string, sourceId: string): Promise<ClaimListItem[]> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${sourceId}/claims`);
  return response.json() as Promise<ClaimListItem[]>;
}
