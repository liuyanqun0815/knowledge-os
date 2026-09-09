import { useCallback, useEffect, useRef, useState } from "react";
import { approveQuarantine, listQuarantine } from "../api/quarantine";
import type { QuarantineItem } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";

export function QuarantinePage() {
  const { kbId } = useKb();
  const [items, setItems] = useState<QuarantineItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const requestSequence = useRef(0);

  const loadItems = useCallback(async () => {
    if (!kbId) {
      return;
    }

    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    try {
      const result = await listQuarantine(kbId);
      if (requestSequence.current === requestId) {
        setItems(result);
        setError(null);
      }
    } catch {
      if (requestSequence.current === requestId) {
        setError("隔离列表加载失败，请稍后重试。");
      }
    } finally {
      if (requestSequence.current === requestId) {
        setIsLoading(false);
      }
    }
  }, [kbId]);

  useEffect(() => {
    requestSequence.current += 1;
    setItems([]);
    setError(null);
    setNotice(null);
    if (!kbId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    void loadItems();
  }, [kbId, loadItems]);

  async function handleApprove(item: QuarantineItem) {
    if (!kbId) {
      return;
    }

    if (!window.confirm(`确认批准隔离项 #${item.id} 吗？`)) {
      return;
    }

    setError(null);
    setNotice(null);
    setApprovingId(item.id);
    try {
      await approveQuarantine(kbId, item.id);
      setNotice(`隔离项 #${item.id} 已批准。`);
      setIsLoading(true);
      await loadItems();
    } catch {
      setError("隔离项批准失败，请稍后重试。");
    } finally {
      setApprovingId(null);
    }
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可审批隔离项。" />;
  }

  return (
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>隔离审批</h1>
          <p>查看待审批的隔离项，确认后可转为 Claim。</p>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}

      {isLoading ? <p role="status">正在加载隔离项…</p> : null}
      {!isLoading && !error && items.length === 0 ? (
        <EmptyState title="暂无隔离项" description="当前知识库没有待审批的隔离项。" />
      ) : null}
      {items.length > 0 ? (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>原因</th>
                <th>原始数据</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.reason}</td>
                  <td>
                    <details>
                      <summary>查看 JSON</summary>
                      <pre>{JSON.stringify(item.raw, null, 2)}</pre>
                    </details>
                  </td>
                  <td>
                    <button
                      className="button button-primary"
                      type="button"
                      disabled={approvingId === item.id}
                      onClick={() => void handleApprove(item)}
                    >
                      批准
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
