import { type ChangeEvent, Fragment, useCallback, useEffect, useRef, useState } from "react";
import { listClaims } from "../api/claims";
import type { ClaimListItem } from "../api/types";
import { useKb } from "../app/KbContext";
import { ClaimHistoryPanel } from "../components/ClaimHistoryPanel";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";

type StatusFilter = "all" | "active" | "superseded" | "staging" | "quarantined";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "active", label: "生效" },
  { value: "superseded", label: "已取代" },
  { value: "staging", label: "暂存" },
  { value: "quarantined", label: "隔离" },
];

const STATUS_LABELS: Record<string, string> = {
  active: "生效",
  superseded: "已取代",
  staging: "暂存",
  quarantined: "隔离",
};

export function ClaimsPage() {
  const { kbId } = useKb();
  const [claims, setClaims] = useState<ClaimListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [expandedFamilyId, setExpandedFamilyId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const loadClaims = useCallback(async () => {
    if (!kbId) {
      return;
    }

    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    try {
      const items = await listClaims(kbId, {
        status: statusFilter === "all" ? undefined : statusFilter,
        subject: subjectFilter.trim() || undefined,
      });
      if (requestSequence.current === requestId) {
        setClaims(items);
        setError(null);
      }
    } catch {
      if (requestSequence.current === requestId) {
        setError("Claim 列表加载失败，请稍后重试。");
      }
    } finally {
      if (requestSequence.current === requestId) {
        setIsLoading(false);
      }
    }
  }, [kbId, statusFilter, subjectFilter]);

  useEffect(() => {
    requestSequence.current += 1;
    setClaims([]);
    setExpandedFamilyId(null);
    setError(null);
    if (!kbId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    void loadClaims();
  }, [kbId, loadClaims]);

  function handleStatusChange(event: ChangeEvent<HTMLSelectElement>) {
    setStatusFilter(event.target.value as StatusFilter);
  }

  function handleSubjectChange(event: ChangeEvent<HTMLInputElement>) {
    setSubjectFilter(event.target.value);
  }

  function toggleHistory(familyId: string) {
    setExpandedFamilyId((current) => (current === familyId ? null : familyId));
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可浏览 Claim。" />;
  }

  return (
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>Claim 浏览</h1>
          <p>按状态与主体筛选 Claim，点击行查看版本历史。</p>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      <div className="form-card claims-filters">
        <label htmlFor="claim-status">状态</label>
        <select id="claim-status" value={statusFilter} onChange={handleStatusChange}>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <label htmlFor="claim-subject">主体</label>
        <input
          id="claim-subject"
          type="text"
          value={subjectFilter}
          onChange={handleSubjectChange}
          placeholder="按主体筛选"
        />
      </div>

      {isLoading ? <p role="status">正在加载 Claim…</p> : null}
      {!isLoading && !error && claims.length === 0 ? (
        <EmptyState title="暂无 Claim" description="当前筛选条件下没有匹配的 Claim。" />
      ) : null}
      {claims.length > 0 ? (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>主体</th>
                <th>谓词</th>
                <th>客体</th>
                <th>状态</th>
                <th>版本</th>
                <th>置信度</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim) => (
                <Fragment key={claim.id}>
                  <tr
                    className="clickable-row"
                    aria-expanded={expandedFamilyId === claim.family_id}
                    onClick={() => toggleHistory(claim.family_id)}
                  >
                    <td>{claim.subject}</td>
                    <td>{claim.predicate}</td>
                    <td>{claim.object}</td>
                    <td>{STATUS_LABELS[claim.status] ?? claim.status}</td>
                    <td>{claim.version}</td>
                    <td>{claim.confidence.toFixed(2)}</td>
                  </tr>
                  {expandedFamilyId === claim.family_id ? (
                    <tr>
                      <td colSpan={6}>
                        <ClaimHistoryPanel kbId={kbId} familyId={claim.family_id} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
