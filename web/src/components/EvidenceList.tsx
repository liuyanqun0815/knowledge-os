import { useState } from "react";

type EvidenceListProps = {
  evidence: Record<string, unknown>[];
};

function evidenceLabel(item: Record<string, unknown>, index: number): string {
  const span = item.span;
  if (typeof span === "string" && span.trim()) {
    return span;
  }
  const quote = item.quote;
  if (typeof quote === "string" && quote.trim()) {
    return quote;
  }
  return `证据 ${index + 1}`;
}

export function EvidenceList({ evidence }: EvidenceListProps) {
  const [expandedIndexes, setExpandedIndexes] = useState<Set<number>>(new Set());

  if (evidence.length === 0) {
    return <p className="empty-copy">无证据</p>;
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
    <ol className="evidence-list">
      {evidence.map((item, index) => (
        <li key={`${String(item.claim_id ?? "evidence")}-${index}`}>
          <button
            className="expandable-heading"
            type="button"
            aria-expanded={expandedIndexes.has(index)}
            onClick={() => toggle(index)}
          >
            <span>证据 {index + 1}</span>
            <span aria-hidden="true">{expandedIndexes.has(index) ? "收起" : "展开"}</span>
          </button>
          <p>{evidenceLabel(item, index)}</p>
          {expandedIndexes.has(index) ? <pre>{JSON.stringify(item, null, 2)}</pre> : null}
        </li>
      ))}
    </ol>
  );
}
