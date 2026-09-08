import { apiFetch } from "./http";
import type { AskResponse } from "./types";

export type AskQuestionParams = {
  knowledgeBaseId: string;
  question: string;
  sessionId?: string;
  asOf?: string;
};

export async function askQuestion(params: AskQuestionParams): Promise<AskResponse> {
  const body: Record<string, string> = {
    knowledge_base_id: params.knowledgeBaseId,
    question: params.question,
  };
  if (params.sessionId) {
    body.session_id = params.sessionId;
  }
  if (params.asOf) {
    body.as_of = params.asOf;
  }

  const response = await apiFetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<AskResponse>;
}
