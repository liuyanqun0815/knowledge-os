import { apiFetch } from "./http";

export type WikiExportResponse = {
  kb_id: string;
  output_path: string;
  files_written: number;
  source_pages: number;
  entity_pages: number;
  topic_pages?: number;
  exported_at: string;
};

export type WikiExportOptions = {
  output_dir?: string | null;
  use_llm?: boolean;
};

export async function exportWiki(kbId: string, options: WikiExportOptions = {}): Promise<WikiExportResponse> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      output_dir: options.output_dir ?? null,
      use_llm: options.use_llm ?? false,
    }),
  });
  return response.json() as Promise<WikiExportResponse>;
}

export type WikiCompileResponse = {
  kb_id: string;
  wiki_root: string;
  pages_written: number;
  topics: string[];
  source_ids: string[];
};

/** Compile into `{data_root}/kb/{kbId}/wiki/` (same root as Wiki browser). */
export async function compileWiki(kbId: string, sourceId?: string): Promise<WikiCompileResponse> {
  const params = sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : "";
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/compile${params}`, {
    method: "POST",
  });
  return response.json() as Promise<WikiCompileResponse>;
}

/** Download compiled wiki tree as a zip (same layout as the left sidebar). */
export async function downloadWikiZip(kbId: string): Promise<void> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/download`);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `${kbId}-wiki.zip`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export type WikiTreePageItem = { page_id: string; title: string; summary?: string | null };
export type WikiTreeHubItem = { name: string; description?: string | null; pages: WikiTreePageItem[] };
export type WikiTreeResponse = { kb_id: string; wiki_root: string; hubs: WikiTreeHubItem[] };
export type WikiPageResponse = { page_id: string; title: string; path: string; markdown: string };
export type WikiSearchHit = { page_id: string; title: string; snippets: string[] };
export type WikiSearchResponse = { query: string; total: number; hits: WikiSearchHit[] };

export async function fetchWikiTree(kbId: string): Promise<WikiTreeResponse> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/tree`);
  return response.json();
}

export async function fetchWikiPage(kbId: string, pageId: string): Promise<WikiPageResponse> {
  const encoded = pageId.split("/").map(encodeURIComponent).join("/");
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/pages/${encoded}`);
  return response.json();
}

export async function searchWiki(kbId: string, q: string, limit = 50): Promise<WikiSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/search?${params}`);
  return response.json();
}
