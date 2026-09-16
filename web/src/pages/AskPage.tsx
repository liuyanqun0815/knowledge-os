import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { askQuestion, fetchTrace } from "../api/ask";
import { useKb } from "../app/KbContext";
import { AskMessageBubble } from "../components/AskMessageBubble";
import { EmptyState } from "../components/EmptyState";
import type { AskChatMessage } from "./askTypes";

function newMessageId(): string {
  return crypto.randomUUID();
}

export function AskPage() {
  const { kbId } = useKb();
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<AskChatMessage[]>([]);
  const [question, setQuestion] = useState("");
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

  async function submitQuestion() {
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion();
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitQuestion();
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

      <div className="ask-chat-shell">
        <div className="ask-chat-messages" role="log" aria-live="polite">
          {messages.length === 0 ? (
            <div className="ask-chat-empty">
              <p className="ask-chat-empty-title">开始提问</p>
              <p>输入问题开始对话。切换知识库会清空当前会话。</p>
            </div>
          ) : (
            messages.map((message) => <AskMessageBubble key={message.id} message={message} />)
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="ask-chat-composer" onSubmit={handleSubmit}>
          <textarea
            id="ask-question"
            aria-label="问题"
            rows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="输入问题…"
            disabled={isAsking}
          />
          <div className="ask-chat-composer-bar">
            <span className="ask-chat-composer-hint">Enter 发送 · Shift+Enter 换行</span>
            <button className="button button-primary ask-chat-send" type="submit" disabled={isAsking || !question.trim()}>
              {isAsking ? "提问中…" : "发送"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
