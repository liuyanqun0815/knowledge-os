import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getKnowledgeBase, updateKnowledgeBase } from "../api/knowledgeBases";
import { listSources } from "../api/sources";
import type { KnowledgeBase, SourceItem } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { SourceFileBrowser } from "../components/SourceFileBrowser";
import { DOMAIN_TYPE_OPTIONS, domainTypeLabel, type DomainTypeValue } from "../domainTypes";

function asDomainType(value: string): DomainTypeValue {
  const matched = DOMAIN_TYPE_OPTIONS.find((item) => item.value === value);
  return matched?.value ?? "generic";
}

export function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [name, setName] = useState("");
  const [domainType, setDomainType] = useState<DomainTypeValue>("generic");
  const [description, setDescription] = useState("");
  const [graphEnabled, setGraphEnabled] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
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
          setDomainType(asDomainType(item.domain_type));
          setDescription(item.description);
          setGraphEnabled(item.graph_enabled === true);
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
        domain_type: domainType,
        description: description.trim(),
        graph_enabled: graphEnabled,
      });
      setKnowledgeBase(updated);
      setName(updated.name);
      setDomainType(asDomainType(updated.domain_type));
      setDescription(updated.description);
      setGraphEnabled(updated.graph_enabled === true);
      window.dispatchEvent(new CustomEvent("akos:kb-list-changed"));
      setNotice("修改已保存。");
    } catch {
      setError("知识库保存失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleArchive() {
    if (!id || !window.confirm("确定删除该知识库吗？删除后将从列表中隐藏（数据仍保留，可联系管理员恢复）。")) {
      return;
    }

    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      const updated = await updateKnowledgeBase(id, { status: "archived" });
      setKnowledgeBase(updated);
      window.dispatchEvent(new CustomEvent("akos:kb-list-changed"));
      setNotice("知识库已删除。");
    } catch {
      setError("知识库删除失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  if (error && !knowledgeBase) {
    return <ErrorBanner message={error} />;
  }

  if (!knowledgeBase || !id) {
    return <p role="status">正在加载知识库…</p>;
  }

  return (
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>{knowledgeBase.name}</h1>
          <p>
            {domainTypeLabel(knowledgeBase.domain_type)} ·{" "}
            {knowledgeBase.status === "active" ? "知识库启用" : "已归档"} ·{" "}
            {knowledgeBase.graph_enabled ? "图谱已开启" : "图谱已关闭"}
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-secondary" to={`/sources?kb=${id}`}>
            管理文档
          </Link>
          <Link className="button button-secondary" to={`/wiki?kb=${id}`}>
            打开 Wiki
          </Link>
          <Link className="button button-primary" to={`/ask?kb=${id}`}>
            开始问答
          </Link>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}
      <form className="form-card kb-settings-card" onSubmit={handleSave}>
        <div className="kb-settings-fields">
          <div className="kb-settings-field">
            <label htmlFor="knowledge-base-name">名称</label>
            <input
              id="knowledge-base-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div className="kb-settings-field">
            <label htmlFor="knowledge-base-domain">领域类型</label>
            <select
              id="knowledge-base-domain"
              value={domainType}
              onChange={(event) => setDomainType(event.target.value as DomainTypeValue)}
              disabled={knowledgeBase.status === "archived"}
            >
              {DOMAIN_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}（{option.value}）
                </option>
              ))}
            </select>
          </div>
          <div className="kb-settings-field">
            <label htmlFor="knowledge-base-description">描述</label>
            <textarea
              id="knowledge-base-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
              placeholder="可选，简要说明知识库用途"
            />
          </div>
          <label className="form-checkbox-row" htmlFor="knowledge-base-graph">
            <input
              id="knowledge-base-graph"
              type="checkbox"
              checked={graphEnabled}
              onChange={(event) => setGraphEnabled(event.target.checked)}
              disabled={knowledgeBase.status === "archived"}
            />
            <span>
              开启知识图谱
              <small className="form-hint">关闭后不再写入实体/关系，也不参与问答图谱召回；已有图数据保留。</small>
            </span>
          </label>
        </div>

        <div className="form-actions form-actions-between">
          <button
            className="button button-danger"
            type="button"
            disabled={isSaving || knowledgeBase.status === "archived"}
            onClick={handleArchive}
          >
            {knowledgeBase.status === "archived" ? "已删除" : "删除知识库"}
          </button>
          <button className="button button-primary" type="submit" disabled={isSaving || knowledgeBase.status === "archived"}>
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
