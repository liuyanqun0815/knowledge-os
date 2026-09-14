import { useState } from "react";
import type { AgentTraceStep } from "../api/types";
import { EvidenceList } from "./EvidenceList";
import { TraceStepDetail } from "./TraceStepDetail";

export type AskExecutionCardProps = {
  steps: AgentTraceStep[];
  unavailableReason?: string;
  evidence?: Record<string, unknown>[];
};

const NODE_LABELS: Record<string, string> = {
  recall: "会话回忆",
  parse_time: "时间解析",
  normalize: "问题归一化",
  route_mode: "路由检索",
  retrieve: "混合检索",
  verify: "Claim 核验",
  explain: "证据解释",
  synthesize: "LLM 综合",
  answer: "生成回答",
  remember: "写入记忆",
};

function formatDurationMs(value: number | null | undefined): string {
  if (value == null || value < 0) {
    return "—";
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  return `${(value / 1000).toFixed(2)} 秒`;
}

function statusIcon(status: AgentTraceStep["status"]): string {
  switch (status) {
    case "ok":
      return "✓";
    case "error":
      return "✕";
    case "skipped":
      return "–";
    default:
      return "✓";
  }
}

export function AskExecutionCard({
  steps,
  unavailableReason = "轨迹暂不可用",
  evidence,
}: AskExecutionCardProps): JSX.Element {
  const [cardOpen, setCardOpen] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());

  function toggleStep(index: number) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  return (
    <section className="ask-exec-card">
      <button
        type="button"
        className="ask-exec-card-header"
        aria-expanded={cardOpen}
        onClick={() => setCardOpen((open) => !open)}
      >
        <span>执行结果 · {steps.length} 步</span>
        <span className="ask-exec-chevron" aria-hidden="true">
          {cardOpen ? "▾" : "▸"}
        </span>
      </button>

      {cardOpen ? (
        steps.length === 0 ? (
          <p className="empty-copy">{unavailableReason}</p>
        ) : (
          <ol className="ask-exec-steps">
            {steps.map((step, index) => {
              const status = step.status ?? "ok";
              const label = NODE_LABELS[step.node] ?? step.node;
              const isExpanded = expanded.has(index);
              return (
                <li key={`${step.node}-${index}`} className="ask-exec-step" data-status={status}>
                  <button
                    type="button"
                    className="ask-exec-step-toggle"
                    aria-expanded={isExpanded}
                    onClick={() => toggleStep(index)}
                  >
                    <span className="ask-exec-step-label">
                      <span className="ask-exec-status" aria-hidden="true">
                        {statusIcon(status)}
                      </span>
                      {label}
                    </span>
                    <span className="ask-exec-step-meta">
                      <span>{formatDurationMs(step.duration_ms)}</span>
                      <span className="ask-exec-chevron" aria-hidden="true">
                        {isExpanded ? "▾" : "▸"}
                      </span>
                    </span>
                  </button>
                  {isExpanded ? (
                    <div className="ask-exec-step-body">
                      {step.summary ? <p className="ask-exec-step-summary">{step.summary}</p> : null}
                      {step.detail !== undefined &&
                      typeof step.detail === "object" &&
                      step.detail !== null &&
                      !Array.isArray(step.detail) ? (
                        <TraceStepDetail node={step.node} detail={step.detail as Record<string, unknown>} />
                      ) : step.detail !== undefined ? (
                        <pre>{JSON.stringify(step.detail, null, 2)}</pre>
                      ) : null}
                      {step.node === "verify" && evidence && evidence.length > 0 ? (
                        <div className="ask-exec-step-evidence">
                          <h3>证据</h3>
                          <EvidenceList evidence={evidence} />
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ol>
        )
      ) : null}
    </section>
  );
}
