import { useState } from "react";
import type { AgentTraceStep } from "../api/types";
import { TraceStepDetail } from "./TraceStepDetail";

type TraceTimelineProps = {
  steps: AgentTraceStep[];
  unavailableReason?: string;
};

const STATUS_LABELS: Record<AgentTraceStep["status"], string> = {
  ok: "完成",
  error: "失败",
  skipped: "已跳过",
};

const NODE_LABELS: Record<string, string> = {
  recall: "会话回忆",
  parse_time: "时间解析",
  normalize: "问题归一化",
  route_mode: "路由检索",
  retrieve: "混合检索",
  rerank: "相关性重排",
  verify: "Claim 核验",
  explain: "证据解释",
  synthesize: "LLM 综合",
  answer: "生成回答",
  remember: "写入记忆",
};

export function TraceTimeline({ steps, unavailableReason = "轨迹暂不可用" }: TraceTimelineProps) {
  const [expandedIndexes, setExpandedIndexes] = useState<Set<number>>(new Set());

  if (steps.length === 0) {
    return <p className="empty-copy">{unavailableReason}</p>;
  }

  function toggle(index: number) {
    setExpandedIndexes((current) => {
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
    <ol className="trace-timeline">
      {steps.map((step, index) => {
        const status = step.status ?? "ok";
        const label = NODE_LABELS[step.node] ?? step.node;
        const canExpand = step.detail !== undefined;
        return (
          <li key={`${step.node}-${index}`} data-status={status}>
            <button
              className="expandable-heading"
              type="button"
              aria-expanded={expandedIndexes.has(index)}
              onClick={() => toggle(index)}
              disabled={!canExpand}
            >
              <span>{label}</span>
              <span>{STATUS_LABELS[status]}</span>
            </button>
            {step.summary ? <p>{step.summary}</p> : null}
            {step.duration_ms !== undefined ? <small>{step.duration_ms} ms</small> : null}
            {expandedIndexes.has(index) && step.detail !== undefined ? (
              typeof step.detail === "object" && step.detail !== null && !Array.isArray(step.detail) ? (
                <TraceStepDetail node={step.node} detail={step.detail as Record<string, unknown>} />
              ) : (
                <pre>{JSON.stringify(step.detail, null, 2)}</pre>
              )
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
