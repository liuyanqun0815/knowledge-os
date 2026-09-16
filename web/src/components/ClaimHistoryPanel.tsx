import { useEffect, useRef, useState } from "react";
import { fetchClaimHistory } from "../api/claims";
import type { ClaimHistoryItem } from "../api/types";

type ClaimHistoryPanelProps = {
  kbId: string;
  familyId: string;
};

const STATUS_LABELS: Record<string, string> = {
  active: "生效",
  superseded: "过期",
  staging: "暂存",
  quarantined: "隔离",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString();
}

export function ClaimHistoryPanel({ kbId, familyId }: ClaimHistoryPanelProps) {
  const [history, setHistory] = useState<ClaimHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    setIsLoading(true);
    setError(null);

    fetchClaimHistory(kbId, familyId)
      .then((items) => {
        if (requestSequence.current === requestId) {
          setHistory(items);
        }
      })
      .catch(() => {
        if (requestSequence.current === requestId) {
          setError("版本历史加载失败，请稍后重试。");
        }
      })
      .finally(() => {
        if (requestSequence.current === requestId) {
          setIsLoading(false);
        }
      });
  }, [familyId, kbId]);

  if (isLoading) {
    return <p role="status">正在加载版本历史…</p>;
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (history.length === 0) {
    return <p className="empty-copy">暂无版本历史</p>;
  }

  return (
    <ol className="trace-timeline" aria-label="Claim 版本时间线">
      {history.map((item) => (
        <li key={item.id} data-status={item.status}>
          <div className="expandable-heading" aria-disabled="true">
            <span>
              v{item.version} · {item.subject}
            </span>
            <span>{STATUS_LABELS[item.status] ?? item.status}</span>
          </div>
          <p>
            {item.predicate} → {item.object}
          </p>
          <small>
            生效：{formatDate(item.valid_from)} · 失效：{formatDate(item.valid_to)}
          </small>
          {item.source_ids.length > 0 ? <small>来源：{item.source_ids.join(", ")}</small> : null}
        </li>
      ))}
    </ol>
  );
}
