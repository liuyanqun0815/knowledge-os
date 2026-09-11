import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getKnowledgeBase, updateKnowledgeBase } from "../api/knowledgeBases";
import { listSources } from "../api/sources";
import { exportWiki } from "../api/wiki";
import type { KnowledgeBase, SourceItem } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { SourceFileBrowser } from "../components/SourceFileBrowser";

export function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(null);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const sourceRequestSequence = useRef(0);

  const loadSources = useCallback(async () => {
    if (!id) {
      return;
    }
    const requestId = sourceRequestSequence.current + 1;
    sourceRequestSequence.current = requestId;
    try {
      const items = await listSources(id, { query: searchQuery });
      if (sourceRequestSequence.current === requestId) {
        setSources(items);
        setSourcesError(null);
      }
    } catch {
      if (sourceRequestSequence.current === requestId) {
        setSourcesError("文档列表加载失败。");
      }
    }
  }, [id, searchQuery]);

  useEffect(() => {
    if (!id) {
      setError("缺少知识库 ID。");
      return;
    }

    let active = true;
    getKnowledgeBase(id)
      .then((item) => {
        if (active) {
          setKnowledgeBase(item);
          setName(item.name);
          setDescription(item.description);
        }
      })
      .catch(() => {
        if (active) {
          setError("知识库详情加载失败，请稍后重试。");
        }
      });

    return () => {
      active = false;
    };
  }, [id]);

  useEffect(() => {
    if (!id) {
      return;
    }
    const timer = window.setTimeout(() => {
      void loadSources();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [id, loadSources]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!id) {
      return;
    }

    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      const updated = await updateKnowledgeBase(id, {
        name: name.trim(),
        description: description.trim(),
      });
      setKnowledgeBase(updated);
      setName(updated.name);
      setDescription(updated.description);
      setNotice("修改已保存。");
    } catch {
      setError("知识库保存失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleArchive() {
    if (!id || !window.confirm("归档后该知识库将不再出现在默认列表中，确认继续吗？")) {
      return;
    }

    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      const updated = await updateKnowledgeBase(id, { status: "archived" });
      setKnowledgeBase(updated);
      window.dispatchEvent(new CustomEvent("akos:kb-list-changed"));
      setNotice("知识库已归档。");
    } catch {
      setError("知识库归档失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleExportWiki() {
    if (!id) {
      return;
    }
    setError(null);
    setNotice(null);
    setIsExporting(true);
    try {
      const result = await exportWiki(id);
      const topicHint =
        result.topic_pages && result.topic_pages > 0 ? `（含 ${result.topic_pages} 个主题）` : "";
      setNotice(`Wiki 已导出：${result.files_written} 个文件${topicHint} → ${result.output_path}`);
    } catch {
      setError("Wiki 导出失败，请稍后重试。");
    } finally {
      setIsExporting(false);
    }
  }

  if (error && !knowledgeBase) {
    return <ErrorBanner message={error} />;
  }

  if (!knowledgeBase || !id) {
    return <p role="status">正在加载知识库…</p>;
  }

  return (
    <section className="page-section form-page">
      <div className="page-header">
        <div>
          <h1>{knowledgeBase.name}</h1>
          <p>
            {knowledgeBase.domain_type} · {knowledgeBase.status === "active" ? "启用" : "已归档"}
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-secondary" to={`/sources?kb=${id}`}>
            管理文档
          </Link>
          <button
            className="button button-secondary"
            type="button"
            disabled={isExporting || isSaving}
            onClick={() => void handleExportWiki()}
          >
            {isExporting ? "正在导出…" : "导出 Wiki"}
          </button>
          <Link className="button button-primary" to={`/ask?kb=${id}`}>
            开始问答
          </Link>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}
      <form className="form-card" onSubmit={handleSave}>
        <label htmlFor="knowledge-base-name">名称</label>
        <input
          id="knowledge-base-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />

        <label htmlFor="knowledge-base-description">描述</label>
        <textarea
          id="knowledge-base-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={5}
        />

        <div className="form-actions form-actions-between">
          <button
            className="button button-danger"
            type="button"
            disabled={isSaving || knowledgeBase.status === "archived"}
            onClick={handleArchive}
          >
            {knowledgeBase.status === "archived" ? "已归档" : "归档知识库"}
          </button>
          <button className="button button-primary" type="submit" disabled={isSaving}>
            {isSaving ? "正在保存…" : "保存修改"}
          </button>
        </div>
      </form>

      <section className="result-card">
        <div className="page-header">
          <div>
            <h2>已上传文档</h2>
            <p>按目录浏览本库文件，支持模糊搜索，并可查看每份文档的萃取结果。</p>
          </div>
          <Link className="button button-secondary" to={`/sources?kb=${id}`}>
            前往文档管理
          </Link>
        </div>
        {sourcesError ? <ErrorBanner message={sourcesError} /> : null}
        <SourceFileBrowser
          kbId={id}
          sources={sources}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          expandedSourceId={expandedSourceId}
          onToggleSource={(sourceId) => setExpandedSourceId((current) => (current === sourceId ? null : sourceId))}
          onChanged={loadSources}
          onError={setSourcesError}
        />
      </section>
    </section>
  );
}
