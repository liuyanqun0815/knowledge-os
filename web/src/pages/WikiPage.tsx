import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchWikiPage,
  fetchWikiTree,
  searchWiki,
  type WikiPageResponse,
  type WikiSearchHit,
  type WikiTreeResponse,
} from "../api/wiki";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { WikiMarkdown } from "../components/WikiMarkdown";
import { WikiSidebar } from "../components/WikiSidebar";

function collectPageIds(tree: WikiTreeResponse | null): Set<string> {
  const ids = new Set<string>();
  if (!tree) {
    return ids;
  }
  for (const hub of tree.hubs) {
    for (const page of hub.pages) {
      ids.add(page.page_id);
    }
  }
  return ids;
}

function pickDefaultPageId(tree: WikiTreeResponse): string | null {
  const pageIds = collectPageIds(tree);
  if (pageIds.has("index")) {
    return "index";
  }
  return tree.hubs[0]?.pages[0]?.page_id ?? null;
}

export function WikiPage() {
  const { kbId } = useKb();
  const [searchParams, setSearchParams] = useSearchParams();
  const pageParam = searchParams.get("page");
  const queryParam = searchParams.get("q") ?? "";

  const [tree, setTree] = useState<WikiTreeResponse | null>(null);
  const [article, setArticle] = useState<WikiPageResponse | null>(null);
  const [searchHits, setSearchHits] = useState<WikiSearchHit[] | null>(null);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchDraft, setSearchDraft] = useState(queryParam);
  const [isLoadingTree, setIsLoadingTree] = useState(false);
  const [isLoadingPage, setIsLoadingPage] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const treeRequestRef = useRef(0);
  const pageRequestRef = useRef(0);
  const searchRequestRef = useRef(0);
  const prevKbIdRef = useRef<string | null | undefined>(undefined);

  const hubs = useMemo(() => tree?.hubs ?? [], [tree]);
  const pageIds = useMemo(() => collectPageIds(tree), [tree]);
  const activePageId = pageParam;

  useEffect(() => {
    setSearchDraft(queryParam);
  }, [queryParam]);

  useEffect(() => {
    const prevKbId = prevKbIdRef.current;
    if (prevKbId === kbId) {
      return;
    }
    const hadPreviousKb = prevKbId !== undefined;
    prevKbIdRef.current = kbId;

    treeRequestRef.current += 1;
    pageRequestRef.current += 1;
    searchRequestRef.current += 1;
    setTree(null);
    setArticle(null);
    setSearchHits(null);
    setSearchTotal(0);
    setError(null);
    if (!kbId) {
      setIsLoadingTree(false);
      setIsLoadingPage(false);
      setIsSearching(false);
    }
    if (hadPreviousKb) {
      setSearchParams(
        (current) => {
          if (!current.get("page")) {
            return current;
          }
          const next = new URLSearchParams(current);
          next.delete("page");
          return next;
        },
        { replace: true },
      );
    }
  }, [kbId]);

  useEffect(() => {
    if (!kbId) {
      return;
    }

    const requestId = treeRequestRef.current + 1;
    treeRequestRef.current = requestId;
    setIsLoadingTree(true);

    void (async () => {
      try {
        const nextTree = await fetchWikiTree(kbId);
        if (treeRequestRef.current !== requestId) {
          return;
        }
        setTree(nextTree);
        setError(null);

        const nextPageIds = collectPageIds(nextTree);
        setSearchParams(
          (current) => {
            const currentPage = current.get("page");
            if (currentPage && nextPageIds.has(currentPage)) {
              return current;
            }
            const defaultPage = pickDefaultPageId(nextTree);
            const next = new URLSearchParams(current);
            if (defaultPage) {
              next.set("page", defaultPage);
            } else {
              next.delete("page");
            }
            return next;
          },
          { replace: true },
        );
      } catch {
        if (treeRequestRef.current === requestId) {
          setError("Wiki 目录加载失败，请稍后重试。");
          setTree(null);
        }
      } finally {
        if (treeRequestRef.current === requestId) {
          setIsLoadingTree(false);
        }
      }
    })();
  }, [kbId]);

  useEffect(() => {
    if (!kbId || !pageParam || !tree || tree.kb_id !== kbId || !pageIds.has(pageParam)) {
      return;
    }

    const requestId = pageRequestRef.current + 1;
    pageRequestRef.current = requestId;
    setIsLoadingPage(true);

    void (async () => {
      try {
        const nextPage = await fetchWikiPage(kbId, pageParam);
        if (pageRequestRef.current !== requestId) {
          return;
        }
        setArticle(nextPage);
        setError(null);
      } catch {
        if (pageRequestRef.current === requestId) {
          setError("Wiki 页面加载失败，请稍后重试。");
          setArticle(null);
        }
      } finally {
        if (pageRequestRef.current === requestId) {
          setIsLoadingPage(false);
        }
      }
    })();
  }, [kbId, pageParam, tree, pageIds]);

  useEffect(() => {
    if (!kbId) {
      return;
    }

    const trimmed = queryParam.trim();
    if (!trimmed) {
      searchRequestRef.current += 1;
      setSearchHits(null);
      setSearchTotal(0);
      setIsSearching(false);
      return;
    }

    const requestId = searchRequestRef.current + 1;
    searchRequestRef.current = requestId;
    setIsSearching(true);

    void (async () => {
      try {
        const result = await searchWiki(kbId, trimmed);
        if (searchRequestRef.current !== requestId) {
          return;
        }
        setSearchHits(result.hits);
        setSearchTotal(result.total);
        setError(null);
      } catch {
        if (searchRequestRef.current === requestId) {
          setError("Wiki 搜索失败，请稍后重试。");
          setSearchHits([]);
          setSearchTotal(0);
        }
      } finally {
        if (searchRequestRef.current === requestId) {
          setIsSearching(false);
        }
      }
    })();
  }, [kbId, queryParam]);

  const selectPage = useCallback(
    (pageId: string) => {
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("page", pageId);
        return next;
      });
    },
    [setSearchParams],
  );

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextQuery = searchDraft.trim();
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (nextQuery) {
        next.set("q", nextQuery);
      } else {
        next.delete("q");
      }
      return next;
    });
  }

  function handleClearSearch() {
    setSearchDraft("");
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("q");
      return next;
    });
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可浏览编译 Wiki。" />;
  }

  const trimmedQuery = queryParam.trim();
  const inSearchMode = Boolean(trimmedQuery);
  const isLoading = isLoadingTree || isLoadingPage || isSearching;
  const wikiEmpty = Boolean(tree) && !isLoadingTree && hubs.length === 0 && !inSearchMode;

  if (wikiEmpty) {
    return (
      <section className="page-section wiki-page">
        <div className="page-header">
          <div>
            <h1>Wiki</h1>
            <p>浏览当前知识库的编译 Wiki，支持目录跳转与关键字检索。</p>
          </div>
        </div>
        {error ? <ErrorBanner message={error} /> : null}
        <EmptyState title="暂无 Wiki" description="尚未编译 Wiki，请先完成知识库编译后再浏览。" />
      </section>
    );
  }

  return (
    <section className="page-section wiki-page">
      <div className="page-header">
        <div>
          <h1>Wiki</h1>
          <p>浏览当前知识库的编译 Wiki，支持目录跳转与关键字检索。</p>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {isLoading ? <p role="status">正在加载 Wiki…</p> : null}

      <div className="wiki-layout">
        <aside className="wiki-sidebar-pane">
          <form className="wiki-search" onSubmit={handleSearchSubmit}>
            <label htmlFor="wiki-search-input" className="sr-only">
              搜索 Wiki
            </label>
            <input
              id="wiki-search-input"
              type="search"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              placeholder="搜索关键字…"
            />
            <button className="button button-primary" type="submit">
              搜索
            </button>
            {queryParam ? (
              <button className="button button-secondary" type="button" onClick={handleClearSearch}>
                清空
              </button>
            ) : null}
          </form>

          <WikiSidebar
            hubs={hubs}
            activePageId={activePageId}
            searchHits={inSearchMode ? searchHits : null}
            searchTotal={searchTotal}
            isSearching={inSearchMode && (isSearching || searchHits === null)}
            highlightQuery={trimmedQuery || undefined}
            onSelectPage={selectPage}
          />
        </aside>

        <article className="wiki-article">
          {article ? (
            <WikiMarkdown
              markdown={article.markdown}
              pageIds={pageIds}
              highlightQuery={trimmedQuery || undefined}
              onNavigate={selectPage}
            />
          ) : !isLoading && !error ? (
            <p className="empty-copy">选择左侧页面开始阅读。</p>
          ) : null}
        </article>
      </div>
    </section>
  );
}
