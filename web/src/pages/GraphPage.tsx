import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchGraphNeighbors, fetchGraphSnapshot, listGraphEntities, listGraphPredicates } from "../api/graph";
import type { GraphEdge, GraphEntity } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { ForceGraph } from "../components/ForceGraph";
import { GraphFocusView } from "../components/GraphFocusView";

function mergeEntities(existing: GraphEntity[], incoming: GraphEntity[]): GraphEntity[] {
  const merged = new Map(existing.map((entity) => [entity.id, entity]));
  for (const entity of incoming) {
    merged.set(entity.id, entity);
  }
  return Array.from(merged.values());
}

function mergeEdges(existing: GraphEdge[], incoming: GraphEdge[]): GraphEdge[] {
  const merged = new Map(existing.map((edge) => [`${edge.src}|${edge.predicate}|${edge.dst}`, edge]));
  for (const edge of incoming) {
    merged.set(`${edge.src}|${edge.predicate}|${edge.dst}`, edge);
  }
  return Array.from(merged.values());
}

export function GraphPage() {
  const { kbId } = useKb();
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [searchResults, setSearchResults] = useState<GraphEntity[]>([]);
  const [predicateOptions, setPredicateOptions] = useState<string[]>([]);
  const [totalEntityCount, setTotalEntityCount] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [entitySearch, setEntitySearch] = useState("");
  const [edgePredicate, setEdgePredicate] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [highlightEdgeKeys, setHighlightEdgeKeys] = useState<Set<string>>(new Set());
  const [focusEntities, setFocusEntities] = useState<GraphEntity[]>([]);
  const [focusEdges, setFocusEdges] = useState<GraphEdge[]>([]);
  const [focusLoading, setFocusLoading] = useState(false);
  const requestSequence = useRef(0);
  const highlightTimerRef = useRef<number | null>(null);

  const selectedEntity = useMemo(
    () =>
      entities.find((entity) => entity.id === selectedId) ??
      searchResults.find((entity) => entity.id === selectedId),
    [entities, searchResults, selectedId],
  );

  const loadGraph = useCallback(async () => {
    if (!kbId) {
      return;
    }

    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    try {
      const snapshot = await fetchGraphSnapshot(kbId);
      if (requestSequence.current !== requestId) {
        return;
      }
      setEntities(snapshot.entities);
      setEdges(snapshot.edges);
      setTotalEntityCount(snapshot.entity_total);
      setTruncated(snapshot.truncated);
      setSelectedId(null);
      setSearchResults([]);
      setHasSearched(false);
      setError(null);
    } catch {
      if (requestSequence.current === requestId) {
        setError("图谱加载失败，请稍后重试。");
      }
    } finally {
      if (requestSequence.current === requestId) {
        setIsLoading(false);
      }
    }
  }, [kbId]);

  const loadPredicateOptions = useCallback(async () => {
    if (!kbId) {
      return;
    }
    try {
      const predicates = await listGraphPredicates(kbId, edgePredicate.trim() || undefined);
      setPredicateOptions(predicates);
    } catch {
      setPredicateOptions([]);
    }
  }, [edgePredicate, kbId]);

  const runEntitySearch = useCallback(async () => {
    if (!kbId) {
      return;
    }
    const q = entitySearch.trim();
    const predicate = edgePredicate.trim();
    if (!q && !predicate) {
      setSearchResults([]);
      setHasSearched(false);
      setNotice("请输入实体名称或关系条件后再搜索。");
      return;
    }

    setIsSearching(true);
    setError(null);
    setNotice(null);
    try {
      const results = await listGraphEntities(kbId, { q, predicate });
      setSearchResults(results);
      setHasSearched(true);
      if (results.length > 0) {
        setSelectedId(results[0].id);
      }
      if (results.length === 0) {
        setNotice("未找到匹配的实体。");
      }
    } catch {
      setError("实体搜索失败，请稍后重试。");
    } finally {
      setIsSearching(false);
    }
  }, [edgePredicate, entitySearch, kbId]);

  useEffect(() => {
    requestSequence.current += 1;
    setEntities([]);
    setEdges([]);
    setSearchResults([]);
    setPredicateOptions([]);
    setTotalEntityCount(0);
    setSelectedId(null);
    setEntitySearch("");
    setEdgePredicate("");
    setHasSearched(false);
    setTruncated(false);
    setError(null);
    setNotice(null);
    if (!kbId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    void loadGraph();
  }, [kbId, loadGraph]);

  useEffect(() => {
    if (!kbId || !edgePredicate.trim()) {
      return;
    }
    const timer = window.setTimeout(() => {
      void loadPredicateOptions();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [edgePredicate, kbId, loadPredicateOptions]);

  const loadFocusSubgraph = useCallback(
    async (entityId: string) => {
      if (!kbId) {
        return;
      }
      const center =
        entities.find((item) => item.id === entityId) ?? searchResults.find((item) => item.id === entityId);
      if (!center) {
        return;
      }

      setFocusLoading(true);
      try {
        const response = await fetchGraphNeighbors(kbId, entityId);
        const localEdges = edges.filter((edge) => edge.src === entityId || edge.dst === entityId);
        const relatedIds = new Set<string>([entityId]);
        for (const edge of [...response.edges, ...localEdges]) {
          relatedIds.add(edge.src);
          relatedIds.add(edge.dst);
        }
        const knownEntities = mergeEntities(entities, searchResults).filter((item) => relatedIds.has(item.id));
        setFocusEntities(mergeEntities([center], mergeEntities(response.entities, knownEntities)));
        setFocusEdges(mergeEdges(response.edges, localEdges));
      } catch {
        setFocusEntities([center]);
        setFocusEdges(edges.filter((edge) => edge.src === entityId || edge.dst === entityId));
      } finally {
        setFocusLoading(false);
      }
    },
    [edges, entities, kbId, searchResults],
  );

  useEffect(() => {
    if (!selectedId) {
      setFocusEntities([]);
      setFocusEdges([]);
      return;
    }
    void loadFocusSubgraph(selectedId);
  }, [loadFocusSubgraph, selectedId]);

  function handleSelectNode(entityId: string) {
    setSelectedId(entityId);
  }

  function handleDeselectNode() {
    setSelectedId(null);
  }

  async function handleExpand(entityId: string) {
    if (!kbId) {
      return;
    }

    setIsExpanding(true);
    setError(null);
    setNotice(null);
    try {
      const predicate = edgePredicate.trim();
      const response = await fetchGraphNeighbors(
        kbId,
        entityId,
        predicate ? { predicates: [predicate] } : undefined,
      );
      setEntities((current) => mergeEntities(current, response.entities));
      setEdges((current) => mergeEdges(current, response.edges));
      setSearchResults((current) => mergeEntities(current, response.entities));
      setSelectedId(entityId);
      const expandedKeys = new Set(response.edges.map((edge) => `${edge.src}|${edge.predicate}|${edge.dst}`));
      setHighlightEdgeKeys(expandedKeys);
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
      highlightTimerRef.current = window.setTimeout(() => {
        setHighlightEdgeKeys(new Set());
      }, 5000);
      await loadFocusSubgraph(entityId);
      if (response.edges.length === 0) {
        setNotice(`实体「${selectedEntity?.name ?? entityId}」没有更多出边邻居。`);
      } else {
        setNotice(`已展开 ${response.edges.length} 条关系。`);
      }
    } catch {
      setError("邻居展开失败，请稍后重试。");
    } finally {
      setIsExpanding(false);
    }
  }

  function handleEntitySearchChange(event: ChangeEvent<HTMLInputElement>) {
    setEntitySearch(event.target.value);
  }

  function handleEdgePredicateChange(event: ChangeEvent<HTMLInputElement>) {
    setEdgePredicate(event.target.value);
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可浏览知识图谱。" />;
  }

  return (
    <section className="page-section graph-page">
      <div className="page-header">
        <div>
          <h1>知识图谱</h1>
          <p>浏览实体与关系，支持邻居展开探索关联知识。</p>
        </div>
        <div className="header-actions">
          <button className="button button-secondary" type="button" disabled={isLoading} onClick={() => void loadGraph()}>
            刷新
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={!selectedId || isExpanding}
            onClick={() => selectedId && void handleExpand(selectedId)}
          >
            {isExpanding ? "展开中…" : "展开邻居"}
          </button>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}
      {truncated ? (
        <p className="info-banner">
          图谱仅展示生效状态的 Claim 关系；数据较多时画布只显示部分实体/关系，请通过搜索与邻居展开继续探索。
        </p>
      ) : null}

      {isLoading ? <p role="status">正在加载图谱…</p> : null}

      {!isLoading && !error && entities.length === 0 ? (
        <EmptyState title="暂无图谱数据" description="请先上传并编译文档，系统会在入库时生成实体与关系。" />
      ) : null}

      {!isLoading && entities.length > 0 ? (
        <div className="graph-layout">
          <aside className="graph-sidebar">
            <div className="graph-search-panel">
              <h2 className="graph-search-label">搜索实体</h2>
              <label className="graph-field-label" htmlFor="graph-search">
                实体名称 / ID
              </label>
              <input
                id="graph-search"
                className="graph-search-input"
                value={entitySearch}
                onChange={handleEntitySearchChange}
                placeholder="按名称或 ID 搜索"
              />
              <label className="graph-field-label" htmlFor="graph-predicate">
                关系条件（谓词）
              </label>
              <input
                id="graph-predicate"
                className="graph-search-input"
                value={edgePredicate}
                onChange={handleEdgePredicateChange}
                placeholder="如：适用类目、运费承担方"
                list="graph-predicate-options"
              />
              <datalist id="graph-predicate-options">
                {predicateOptions.map((predicate) => (
                  <option key={predicate} value={predicate} />
                ))}
              </datalist>
              <button
                className="button button-primary graph-search-button"
                type="button"
                disabled={isSearching}
                onClick={() => void runEntitySearch()}
              >
                {isSearching ? "搜索中…" : "搜索"}
              </button>
              <p className="graph-sidebar-meta">
                仅展示生效 Claim；库内 {totalEntityCount} 个生效相关实体，画布 {entities.length} 节点 /{" "}
                {edges.length} 边
              </p>
            </div>

            {!hasSearched ? (
              <p className="graph-search-placeholder">输入实体名称或关系条件后点击搜索，结果将显示在此处。</p>
            ) : null}

            {hasSearched ? (
              <ul className="graph-entity-list">
                {searchResults.length === 0 ? (
                  <li className="graph-search-empty">无匹配实体</li>
                ) : (
                  searchResults.map((entity) => (
                    <li key={entity.id}>
                      <button
                        type="button"
                        className={entity.id === selectedId ? "graph-entity-item active" : "graph-entity-item"}
                        onClick={() => handleSelectNode(entity.id)}
                      >
                        <span className="graph-entity-name">{entity.name}</span>
                        <span className="graph-entity-type">{entity.type}</span>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            ) : null}
          </aside>

          <div className="graph-canvas-panel">
            <ForceGraph
              entities={entities}
              edges={edges}
              selectedId={selectedId}
              highlightEdgeKeys={highlightEdgeKeys}
              onSelect={handleSelectNode}
              onDeselect={handleDeselectNode}
              onExpand={(entityId) => void handleExpand(entityId)}
            />

            {selectedEntity ? (
              <GraphFocusView
                center={selectedEntity}
                entities={focusEntities.length > 0 ? focusEntities : [selectedEntity]}
                edges={focusEdges}
                selectedId={selectedId}
                isLoading={focusLoading}
                onSelect={handleSelectNode}
              />
            ) : (
              <div className="graph-focus-placeholder">
                <h3>关联视图</h3>
                <p>点击上方画布中的节点，此处将单独展示该节点及直接关联实体。</p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
