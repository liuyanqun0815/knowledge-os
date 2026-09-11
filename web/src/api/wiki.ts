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
