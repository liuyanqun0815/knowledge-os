import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listKnowledgeBases } from "../api/knowledgeBases";
import type { KnowledgeBase } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";

export function KnowledgeBaseListPage() {
  const navigate = useNavigate();
  const { kbId, setKbId } = useKb();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    listKnowledgeBases()
      .then((items) => {
        if (active) {
          setKnowledgeBases(items);
        }
      })
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
