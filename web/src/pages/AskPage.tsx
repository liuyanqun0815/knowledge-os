import { type FormEvent, useEffect, useRef, useState } from "react";
import { askQuestion } from "../api/ask";
import type { AskResponse } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { EvidenceList } from "../components/EvidenceList";
import { TraceTimeline } from "../components/TraceTimeline";

export function AskPage() {
  const { kbId } = useKb();
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [isAsking, setIsAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    requestSequence.current += 1;
    setResult(null);
    setError(null);
    setIsAsking(false);
  }, [kbId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!kbId || !question.trim()) {
      return;
    }

    setIsAsking(true);
    setError(null);
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    try {
      const response = await askQuestion({
        knowledgeBaseId: kbId,
        question: question.trim(),
        ...(asOf ? { asOf: new Date(asOf).toISOString() } : {}),
      });
      if (requestSequence.current === requestId) {
        setResult(response);
      }
    } catch {
      if (requestSequence.current === requestId) {
        setResult(null);
        setError("提问失败，请稍后重试。");
      }
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
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>知识问答</h1>
          <p>基于当前知识库提问，并核验回答证据和执行轨迹。</p>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      <form className="form-card ask-form" onSubmit={handleSubmit}>
        <label htmlFor="ask-question">问题</label>
        <textarea
          id="ask-question"
          rows={4}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="请输入要查询的问题"
          disabled={isAsking}
        />
        <label htmlFor="ask-as-of">截至时间（可选）</label>
        <input
          id="ask-as-of"
          type="datetime-local"
          value={asOf}
          onChange={(event) => setAsOf(event.target.value)}
          disabled={isAsking}
        />
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={isAsking || !question.trim()}>
            {isAsking ? "提问中…" : "提问"}
          </button>
        </div>
      </form>

      {result ? (
        <div className="ask-result">
          <article className="result-card">
            <h2>回答</h2>
            <p className="answer-text">{result.text}</p>
            <dl className="answer-meta">
              <div>
                <dt>置信度</dt>
                <dd>{Math.round(result.confidence * 100)}%</dd>
              </div>
              <div>
                <dt>检索模式</dt>
                <dd>{result.retrieval_mode}</dd>
              </div>
            </dl>
          </article>
          <section className="result-card" aria-labelledby="evidence-title">
            <h2 id="evidence-title">证据</h2>
            <EvidenceList evidence={result.evidence} />
          </section>
          <section className="result-card" aria-labelledby="trace-title">
            <h2 id="trace-title">Agent 轨迹</h2>
            <TraceTimeline steps={result.trace ?? []} unavailableReason="轨迹暂不可用" />
          </section>
        </div>
      ) : null}
    </section>
  );
}
