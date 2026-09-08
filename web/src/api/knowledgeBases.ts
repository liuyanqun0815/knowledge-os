import { apiFetch } from "./http";
import type { KnowledgeBase } from "./types";

export type CreateKnowledgeBaseBody = {
  name: string;
  domain_type: string;
  description?: string;
};

export type UpdateKnowledgeBaseBody = {
  name?: string;
  domain_type?: string;
  description?: string;
  status?: "active" | "archived";
};

export async function listKnowledgeBases(includeArchived = false): Promise<KnowledgeBase[]> {
  const query = includeArchived ? "?include_archived=true" : "";
  const response = await apiFetch(`/admin/knowledge-bases${query}`);
  return response.json() as Promise<KnowledgeBase[]>;
}

export async function createKnowledgeBase(body: CreateKnowledgeBaseBody): Promise<KnowledgeBase> {
  const response = await apiFetch("/admin/knowledge-bases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<KnowledgeBase>;
}

export async function getKnowledgeBase(id: string): Promise<KnowledgeBase> {
  const response = await apiFetch(`/admin/knowledge-bases/${id}`);
  return response.json() as Promise<KnowledgeBase>;
}

export async function updateKnowledgeBase(id: string, body: UpdateKnowledgeBaseBody): Promise<KnowledgeBase> {
  const response = await apiFetch(`/admin/knowledge-bases/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<KnowledgeBase>;
}
