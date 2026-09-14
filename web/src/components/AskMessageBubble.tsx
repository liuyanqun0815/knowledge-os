import type { AskChatMessage } from "../pages/askTypes";
import { AskExecutionCard } from "./AskExecutionCard";

function formatClock(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso;
  }
  return parsed.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDurationMs(value: number | null | undefined): string {
  if (value == null || value < 0) {
    return "—";
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  return `${(value / 1000).toFixed(2)} 秒`;
}

function totalDurationMs(message: AskChatMessage): number | undefined {
  const fromResult = message.result?.duration_ms;
  if (typeof fromResult === "number" && fromResult >= 0) {
    return fromResult;
  }
  const steps = message.result?.trace ?? [];
  let sum = 0;
  let found = false;
  for (const step of steps) {
    if (typeof step.duration_ms === "number" && step.duration_ms >= 0) {
      sum += step.duration_ms;
      found = true;
    }
  }
  return found ? sum : undefined;
}

export function AskMessageBubble({ message }: { message: AskChatMessage }): JSX.Element {
  if (message.role === "user") {
    return (
      <article className="ask-chat-bubble ask-chat-bubble-user" data-role="user">
        <p className="ask-chat-bubble-text">{message.text}</p>
        <footer className="ask-chat-bubble-footer">{formatClock(message.createdAt)}</footer>
      </article>
    );
  }

  if (message.status === "pending") {
    return (
      <article className="ask-chat-bubble ask-chat-bubble-assistant" data-role="assistant" data-status="pending">
        <p className="ask-chat-pending">执行中…</p>
      </article>
    );
  }

  if (message.status === "error") {
    return (
      <article className="ask-chat-bubble ask-chat-bubble-assistant" data-role="assistant" data-status="error">
        <p className="ask-chat-error">{message.error ?? "提问失败，请稍后重试。"}</p>
        <footer className="ask-chat-bubble-footer">{formatClock(message.createdAt)}</footer>
      </article>
    );
  }

  const result = message.result;
  const answerText = result?.text ?? message.text;
  const duration = totalDurationMs(message);

  return (
    <article className="ask-chat-bubble ask-chat-bubble-assistant" data-role="assistant" data-status="ok">
      <AskExecutionCard
        steps={result?.trace ?? []}
        evidence={result?.evidence}
        unavailableReason="轨迹暂不可用"
      />
      {answerText ? <p className="ask-chat-answer">{answerText}</p> : null}
      {result ? (
        <dl className="ask-chat-summary">
          <div>
            <dt>置信度</dt>
            <dd>{Math.round(result.confidence * 100)}%</dd>
          </div>
          <div>
            <dt>检索模式</dt>
            <dd>{result.retrieval_mode}</dd>
          </div>
        </dl>
      ) : null}
      <footer className="ask-chat-bubble-footer">
        {formatClock(message.createdAt)} · 耗时 {formatDurationMs(duration)}
      </footer>
    </article>
  );
}
