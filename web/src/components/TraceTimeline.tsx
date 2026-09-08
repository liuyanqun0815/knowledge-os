import { useState } from "react";
import type { AgentTraceStep } from "../api/types";

type TraceTimelineProps = {
  steps: AgentTraceStep[];
  unavailableReason?: string;
};

const STATUS_LABELS: Record<AgentTraceStep["status"], string> = {
  ok: "完成",
  error: "失败",
  skipped: "已跳过",
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
      {steps.map((step, index) => (
        <li key={`${step.node}-${index}`} data-status={step.status}>
          <button
            className="expandable-heading"
            type="button"
            aria-expanded={expandedIndexes.has(index)}
            onClick={() => toggle(index)}
            disabled={step.detail === undefined}
          >
            <span>{step.node}</span>
            <span>{STATUS_LABELS[step.status]}</span>
          </button>
          {step.summary ? <p>{step.summary}</p> : null}
          {step.duration_ms !== undefined ? <small>{step.duration_ms} ms</small> : null}
          {expandedIndexes.has(index) ? <pre>{JSON.stringify(step.detail, null, 2)}</pre> : null}
        </li>
      ))}
    </ol>
  );
}
