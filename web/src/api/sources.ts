import { apiFetch } from "./http";
import type {
  ClaimListItem,
  SourceChunkItem,
  SourceContent,
  SourceItem,
  SourceUploadResponse,
  UploadSourceOptions,
} from "./types";

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

export async function fetchSource(kbId: string, sourceId: string): Promise<SourceItem> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${encodeURIComponent(sourceId)}`);
  const raw = (await response.json()) as BackendSource;
  return mapSource(raw);
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
  if (options.relativePath) {
    formData.append("relative_path", options.relativePath);
  }
  if (options.subjectBindMode) {
    formData.append("subject_bind_mode", options.subjectBindMode);
  }

  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/upload`, {
    method: "POST",
    body: formData,
  });
  return response.json() as Promise<SourceUploadResponse>;
}

export type UploadTreeEntry = {
  file: File;
  relativePath: string;
};

export async function uploadTree(
  kbId: string,
  entries: UploadTreeEntry[],
  options: Pick<UploadSourceOptions, "subjectBindMode"> = {},
): Promise<SourceUploadResponse> {
  const formData = new FormData();
  for (const entry of entries) {
    formData.append("files", entry.file);
    formData.append("relative_paths", entry.relativePath);
  }
  if (options.subjectBindMode) {
    formData.append("subject_bind_mode", options.subjectBindMode);
  }
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/upload-tree`, {
    method: "POST",
    body: formData,
  });
  return response.json() as Promise<SourceUploadResponse>;
}

export async function moveSources(
  kbId: string,
  fromPath: string,
  toPath: string,
): Promise<SourceItem[]> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_path: fromPath, to_path: toPath }),
  });
  const raw = (await response.json()) as BackendSource[];
  return raw.map(mapSource);
}

export async function deleteSource(kbId: string, sourceId: string): Promise<void> {
  await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${sourceId}`, { method: "DELETE" });
}

export async function deleteTree(kbId: string, path: string): Promise<{ deleted_count: number }> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/delete-tree`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  return response.json() as Promise<{ deleted_count: number }>;
}

export async function fetchSourceClaims(kbId: string, sourceId: string): Promise<ClaimListItem[]> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${sourceId}/claims`);
  return response.json() as Promise<ClaimListItem[]>;
}

export async function fetchSourceChunks(
  kbId: string,
  sourceId: string,
  status: "active" | "stale" | "all" = "active",
): Promise<SourceChunkItem[]> {
  const params = new URLSearchParams({ status });
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${sourceId}/chunks?${params}`);
  return response.json() as Promise<SourceChunkItem[]>;
}

export async function fetchSourceContent(kbId: string, sourceId: string): Promise<SourceContent> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/sources/${sourceId}/content`);
  return response.json() as Promise<SourceContent>;
}
