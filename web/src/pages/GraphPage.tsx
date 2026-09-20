import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchGraphNeighbors,
  fetchGraphSnapshot,
  listGraphEntities,
  listGraphPredicates,
  retrieveGraph,
} from "../api/graph";
import type { GraphEdge, GraphEntity, GraphRetrieveHit } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { ForceGraph } from "../components/ForceGraph";
import { GraphFocusView } from "../components/GraphFocusView";

const DEFAULT_ENTITY_LIMIT = 200;
const DEFAULT_EDGE_LIMIT = 500;

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

function clampLimit(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.trunc(value)));
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
  const [entityLimitInput, setEntityLimitInput] = useState(String(DEFAULT_ENTITY_LIMIT));
  const [edgeLimitInput, setEdgeLimitInput] = useState(String(DEFAULT_EDGE_LIMIT));
  const [entityLimit, setEntityLimit] = useState(DEFAULT_ENTITY_LIMIT);
  const [edgeLimit, setEdgeLimit] = useState(DEFAULT_EDGE_LIMIT);
  const [retrieveQuery, setRetrieveQuery] = useState("");
  const [retrieveTopKInput, setRetrieveTopKInput] = useState("20");
  const [retrieveHits, setRetrieveHits] = useState<GraphRetrieveHit[]>([]);
  const [hasRetrieved, setHasRetrieved] = useState(false);
  const [retrieveViewActive, setRetrieveViewActive] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
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

  const loadGraph = useCallback(
    async (limits?: { entityLimit?: number; edgeLimit?: number }) => {
      if (!kbId) {
        return;
      }

      const nextEntityLimit = clampLimit(
        Number(limits?.entityLimit ?? entityLimitInput),
        1,
        1000,
        DEFAULT_ENTITY_LIMIT,
      );
      const nextEdgeLimit = clampLimit(
        Number(limits?.edgeLimit ?? edgeLimitInput),
        1,
        5000,
        DEFAULT_EDGE_LIMIT,
      );
      setEntityLimit(nextEntityLimit);
      setEdgeLimit(nextEdgeLimit);
      setEntityLimitInput(String(nextEntityLimit));
      setEdgeLimitInput(String(nextEdgeLimit));

      const requestId = requestSequence.current + 1;
      requestSequence.current = requestId;
      try {
        const snapshot = await fetchGraphSnapshot(kbId, {
          entityLimit: nextEntityLimit,
          edgeLimit: nextEdgeLimit,
        });
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
        setRetrieveViewActive(false);
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
    },
    [edgeLimitInput, entityLimitInput, kbId],
  );

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

  const runGraphRetrieve = useCallback(async () => {
    if (!kbId) {
      return;
    }
    const query = retrieveQuery.trim();
    if (!query) {
      setNotice("请输入检索文本后再试跑图谱检索。");
      return;
    }
    const topK = clampLimit(Number(retrieveTopKInput), 1, 100, 20);
    setRetrieveTopKInput(String(topK));
    setIsRetrieving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await retrieveGraph(kbId, query, { topK });
      // Invalidate any in-flight snapshot so it cannot overwrite the retrieve subgraph.
      requestSequence.current += 1;
      setRetrieveHits(response.hits);
      setHasRetrieved(true);
      if (response.hits.length === 0) {
        setRetrieveViewActive(false);
        setNotice("图谱检索无命中。可换更贴近实体名称的文本再试。");
      } else {
        setEntities(response.entities ?? []);
        setEdges(response.edges ?? []);
        setTruncated(false);
        setRetrieveViewActive(true);
        setHighlightEdgeKeys(
          new Set((response.edges ?? []).map((edge) => `${edge.src}|${edge.predicate}|${edge.dst}`)),
        );
        if (highlightTimerRef.current !== null) {
          window.clearTimeout(highlightTimerRef.current);
        }
        highlightTimerRef.current = window.setTimeout(() => {
          setHighlightEdgeKeys(new Set());
        }, 8000);
        const entityCount = response.entities?.length ?? 0;
        const edgeCount = response.edges?.length ?? 0;
        setNotice(
          `图谱检索返回 ${response.hit_count} 条关系，右侧已切换为检索子图（${entityCount} 节点 / ${edgeCount} 边）。`,
        );
        const firstEntity = response.hits.find((hit) => hit.entity_id)?.entity_id;
        if (firstEntity) {
          setSelectedId(firstEntity);
        } else {
          setSelectedId(null);
        }
      }
    } catch {
      setError("图谱检索失败，请稍后重试。");
    } finally {
      setIsRetrieving(false);
    }
  }, [kbId, retrieveQuery, retrieveTopKInput]);

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
    setRetrieveQuery("");
    setRetrieveHits([]);
    setHasRetrieved(false);
    setRetrieveViewActive(false);
    setHasSearched(false);
    setTruncated(false);
    setEntityLimit(DEFAULT_ENTITY_LIMIT);
    setEdgeLimit(DEFAULT_EDGE_LIMIT);
    setEntityLimitInput(String(DEFAULT_ENTITY_LIMIT));
    setEdgeLimitInput(String(DEFAULT_EDGE_LIMIT));
    setError(null);
    setNotice(null);
    if (!kbId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    void loadGraph({ entityLimit: DEFAULT_ENTITY_LIMIT, edgeLimit: DEFAULT_EDGE_LIMIT });
    // Only reload when knowledge base changes; limit edits apply on explicit refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kbId]);

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
          <p>浏览实体与关系，支持邻居展开，并可试跑与问答相同的图谱检索。</p>
        </div>
        <div className="header-actions">
          <button
            className="button button-secondary"
            type="button"
            disabled={isLoading}
            onClick={() => void loadGraph()}
          >
            {retrieveViewActive ? "恢复全图" : "刷新"}
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
      {retrieveViewActive ? (
        <p className="info-banner">
          右侧当前为图谱检索子图（含关系边）。可点击左侧命中项定位节点，或点「恢复全图」回到画布快照。
        </p>
      ) : null}
      {truncated && !retrieveViewActive ? (
        <p className="info-banner">
          当前画布按上限截断：实体 {entityLimit} / 边 {edgeLimit}。库内生效相关实体共 {totalEntityCount}{" "}
          个；可通过提高上限后刷新，或用搜索 / 展开邻居继续探索。
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
              <h2 className="graph-search-label">画布上限</h2>
              <label className="graph-field-label" htmlFor="graph-entity-limit">
                实体上限（1–1000）
              </label>
              <input
                id="graph-entity-limit"
                className="graph-search-input"
                type="number"
                min={1}
                max={1000}
                value={entityLimitInput}
                onChange={(event) => setEntityLimitInput(event.target.value)}
              />
              <label className="graph-field-label" htmlFor="graph-edge-limit">
                边上限（1–5000）
              </label>
              <input
                id="graph-edge-limit"
                className="graph-search-input"
                type="number"
                min={1}
                max={5000}
                value={edgeLimitInput}
                onChange={(event) => setEdgeLimitInput(event.target.value)}
              />
              <p className="graph-sidebar-meta">
                默认 200 / 500。修改后点「刷新」生效。画布 {entities.length} 节点 / {edges.length} 边，库内生效相关{" "}
                {totalEntityCount} 实体。
              </p>
            </div>

            <div className="graph-search-panel">
              <h2 className="graph-search-label">图谱检索试跑</h2>
              <label className="graph-field-label" htmlFor="graph-retrieve-query">
                检索文本
              </label>
              <textarea
                id="graph-retrieve-query"
                className="graph-retrieve-input"
                rows={3}
                value={retrieveQuery}
                onChange={(event) => setRetrieveQuery(event.target.value)}
                placeholder="输入问题或实体相关文本，走与问答相同的 GRAPH 检索"
              />
              <label className="graph-field-label" htmlFor="graph-retrieve-topk">
                返回条数 top_k（1–100）
              </label>
              <input
                id="graph-retrieve-topk"
                className="graph-search-input"
                type="number"
                min={1}
                max={100}
                value={retrieveTopKInput}
                onChange={(event) => setRetrieveTopKInput(event.target.value)}
              />
              <button
                className="button button-primary graph-search-button"
                type="button"
                disabled={isRetrieving}
                onClick={() => void runGraphRetrieve()}
              >
                {isRetrieving ? "检索中…" : "试跑检索"}
              </button>
              {hasRetrieved ? (
                <ul className="graph-retrieve-list">
                  {retrieveHits.length === 0 ? (
                    <li className="graph-search-empty">无命中</li>
                  ) : (
                    retrieveHits.map((hit, index) => (
                      <li key={`${hit.claim_id ?? hit.snippet ?? "hit"}-${index}`}>
                        <button
                          type="button"
                          className={
                            hit.entity_id && hit.entity_id === selectedId
                              ? "graph-retrieve-item active"
                              : "graph-retrieve-item"
                          }
                          disabled={!hit.entity_id}
                          onClick={() => hit.entity_id && handleSelectNode(hit.entity_id)}
                        >
                          <span className="graph-retrieve-score">score {hit.score.toFixed(3)}</span>
                          <span className="graph-retrieve-snippet">{hit.snippet || "（无 snippet）"}</span>
                          <span className="graph-retrieve-meta">
                            {hit.claim_id ? `claim: ${hit.claim_id}` : "claim: —"}
                            {hit.entity_id ? ` · entity: ${hit.entity_id}` : ""}
                          </span>
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              ) : (
                <p className="graph-search-placeholder">试跑结果与后端 GraphPort 一致，Neo4j / Postgres 均可。</p>
              )}
            </div>

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
              key={
                retrieveViewActive
                  ? `retrieve:${entities.length}:${edges.length}:${retrieveHits[0]?.claim_id ?? "none"}`
                  : `snapshot:${entityLimit}:${edgeLimit}:${entities.length}`
              }
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
