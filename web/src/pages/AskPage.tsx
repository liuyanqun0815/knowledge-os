import { type FormEvent, useEffect, useRef, useState } from "react";
import { askQuestion, fetchTrace } from "../api/ask";
import { useKb } from "../app/KbContext";
import { AskMessageBubble } from "../components/AskMessageBubble";
import { EmptyState } from "../components/EmptyState";
import type { AskChatMessage } from "./askTypes";

function toIsoAsOf(localValue: string): string {
  return new Date(localValue).toISOString();
}

function newMessageId(): string {
  return crypto.randomUUID();
}

export function AskPage() {
  const { kbId } = useKb();
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<AskChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [asOfLocal, setAsOfLocal] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const requestSequence = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    requestSequence.current += 1;
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setIsAsking(false);
  }, [kbId]);

  useEffect(() => {
    const el = messagesEndRef.current;
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!kbId || !question.trim() || isAsking) {
      return;
    }

    const trimmed = question.trim();
    const now = new Date().toISOString();
    const userId = newMessageId();
    const assistantId = newMessageId();
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setMessages((current) => [
      ...current,
      {
        id: userId,
        role: "user",
        text: trimmed,
        createdAt: now,
      },
      {
        id: assistantId,
        role: "assistant",
        text: "",
        createdAt: now,
        status: "pending",
      },
    ]);
    setQuestion("");
    setIsAsking(true);

    try {
      const response = await askQuestion({
        knowledgeBaseId: kbId,
        question: trimmed,
        sessionId,
        includeTrace: true,
        ...(asOfLocal ? { asOf: toIsoAsOf(asOfLocal) } : {}),
      });
      if (requestSequence.current !== requestId) {
        return;
      }

      let trace = response.trace ?? [];
      if (trace.length === 0 && response.request_id) {
        try {
          trace = await fetchTrace(kbId, response.request_id);
        } catch {
          trace = [];
        }
      }
      if (requestSequence.current !== requestId) {
        return;
      }

      const result = { ...response, trace };
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                text: result.text,
                status: "ok",
                result,
                createdAt: new Date().toISOString(),
              }
            : message,
        ),
      );
    } catch {
      if (requestSequence.current !== requestId) {
        return;
      }
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                status: "error",
                error: "提问失败，请稍后重试。",
                createdAt: new Date().toISOString(),
              }
            : message,
        ),
      );
    } finally {
      if (requestSequence.current === requestId) {
        setIsAsking(false);
      }
    }
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可提问并查看证据与 Agent 轨迹。" />;
  }

  return (
    <section className="page-section ask-chat-page">
      <div className="page-header">
        <div>
          <h1>知识问答</h1>
          <p>基于当前知识库多轮提问，查看执行步骤与回答。</p>
        </div>
      </div>

      <div className="ask-chat-messages" role="log" aria-live="polite">
        {messages.length === 0 ? (
          <p className="ask-chat-empty">输入问题开始对话。切换知识库会清空当前会话。</p>
        ) : (
          messages.map((message) => <AskMessageBubble key={message.id} message={message} />)
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="ask-chat-composer" onSubmit={handleSubmit}>
        <label htmlFor="ask-question">问题</label>
        <textarea
          id="ask-question"
          rows={3}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="请输入要查询的问题"
          disabled={isAsking}
        />
        <label htmlFor="ask-as-of">截至时间（可选）</label>
        <input
          id="ask-as-of"
          type="datetime-local"
          value={asOfLocal}
          onChange={(event) => setAsOfLocal(event.target.value)}
          disabled={isAsking}
        />
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={isAsking || !question.trim()}>
            {isAsking ? "提问中…" : "提问"}
          </button>
        </div>
      </form>
    </section>
  );
}
