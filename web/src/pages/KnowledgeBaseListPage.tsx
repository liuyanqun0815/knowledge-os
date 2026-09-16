import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { deleteKnowledgeBase, listKnowledgeBases } from "../api/knowledgeBases";
import type { KnowledgeBase } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";

export function KnowledgeBaseListPage() {
  const navigate = useNavigate();
  const { kbId, setKbId, clearKb } = useKb();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function reloadKnowledgeBases() {
    const items = await listKnowledgeBases();
    setKnowledgeBases(items);
    return items;
  }

  useEffect(() => {
    let active = true;

    reloadKnowledgeBases()
      .catch(() => {
        if (active) {
          setError("知识库列表加载失败，请稍后重试。");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleDelete(knowledgeBase: KnowledgeBase) {
    if (
      !window.confirm(
        `确定删除「${knowledgeBase.name}」吗？删除后将从列表中隐藏（数据仍保留，可联系管理员恢复）。`,
      )
    ) {
      return;
    }

    setError(null);
    setDeletingId(knowledgeBase.id);
    try {
      await deleteKnowledgeBase(knowledgeBase.id);
      const remaining = await reloadKnowledgeBases();
      window.dispatchEvent(new CustomEvent("akos:kb-list-changed"));
      if (kbId === knowledgeBase.id) {
        const next = remaining.find((item) => item.status === "active");
        if (next) {
          setKbId(next.id);
        } else {
          clearKb();
        }
      }
    } catch {
      setError("知识库删除失败，请稍后重试。");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>知识库</h1>
          <p>创建和管理不同业务领域的知识库。</p>
        </div>
        <Link className="button button-primary" to="/knowledge-bases/new">
          新建
        </Link>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {isLoading ? <p role="status">正在加载知识库…</p> : null}
      {!isLoading && !error && knowledgeBases.length === 0 ? (
        <EmptyState title="暂无知识库" description="点击“新建”创建第一个知识库。" />
      ) : null}
      {knowledgeBases.length > 0 ? (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>领域类型</th>
                <th>状态</th>
                <th>更新时间</th>
                <th>
                  <span className="sr-only">操作</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {knowledgeBases.map((knowledgeBase) => (
                <tr
                  key={knowledgeBase.id}
                  className="clickable-row"
                  onClick={() => navigate(`/knowledge-bases/${knowledgeBase.id}`)}
                >
                  <td>{knowledgeBase.name}</td>
                  <td>{knowledgeBase.domain_type}</td>
                  <td>{knowledgeBase.status === "active" ? "启用" : "已归档"}</td>
                  <td>{new Date(knowledgeBase.updated_at).toLocaleString()}</td>
                  <td>
                    <div className="table-row-actions">
                      <button
                        className="button button-secondary"
                        type="button"
                        disabled={kbId === knowledgeBase.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          setKbId(knowledgeBase.id);
                        }}
                      >
                        {kbId === knowledgeBase.id ? "当前知识库" : "设为当前"}
                      </button>
                      <button
                        className="button button-danger"
                        type="button"
                        disabled={deletingId === knowledgeBase.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleDelete(knowledgeBase);
                        }}
                      >
                        {deletingId === knowledgeBase.id ? "删除中…" : "删除"}
                      </button>
                    </div>
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
