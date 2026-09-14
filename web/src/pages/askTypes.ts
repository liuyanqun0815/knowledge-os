import type { AskResponse } from "../api/types";

export type AskChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  status?: "pending" | "ok" | "error";
  result?: AskResponse;
  error?: string;
};
