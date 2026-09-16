import { useMemo, useState } from "react";
import type { WikiSearchHit, WikiTreeHubItem } from "../api/wiki";
import { highlightPlainText } from "./wikiHighlight";

export type WikiSidebarProps = {
  hubs: WikiTreeHubItem[];
  activePageId: string | null;
  searchHits: WikiSearchHit[] | null;
  searchTotal?: number;
  isSearching?: boolean;
  highlightQuery?: string;
  onSelectPage: (pageId: string) => void;
};

const INDEX_HUB_NAME = "总览";

function isIndexHub(hub: WikiTreeHubItem): boolean {
  return hub.name === INDEX_HUB_NAME && hub.pages.some((page) => page.page_id === "index");
}

export function WikiSidebar({
  hubs,
  activePageId,
  searchHits,
  searchTotal,
  isSearching = false,
  highlightQuery,
  onSelectPage,
}: WikiSidebarProps) {
  const [expandedHubs, setExpandedHubs] = useState<Set<string>>(() => new Set());

  const indexPage = useMemo(() => {
    const hub = hubs.find(isIndexHub);
    return hub?.pages.find((page) => page.page_id === "index") ?? null;
  }, [hubs]);

  const folderHubs = useMemo(() => hubs.filter((hub) => !isIndexHub(hub)), [hubs]);

  const visibleExpanded = useMemo(() => {
    const next = new Set(expandedHubs);
    for (const hub of folderHubs) {
      if (hub.pages.some((page) => page.page_id === activePageId)) {
        next.add(hub.name);
      }
    }
    return next;
  }, [activePageId, expandedHubs, folderHubs]);

  function toggleHub(name: string) {
    setExpandedHubs((current) => {
      const next = new Set(current);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  if (searchHits !== null || isSearching) {
    if (isSearching && searchHits === null) {
      return (
        <div className="wiki-tree wiki-search-results">
          <p className="wiki-search-meta" role="status">
            正在搜索…
          </p>
        </div>
      );
    }

    const hits = searchHits ?? [];
    return (
      <div className="wiki-tree wiki-search-results">
        <p className="wiki-search-meta" role="status">
          命中 {searchTotal ?? hits.length} 篇
        </p>
        {hits.length === 0 ? (
          <p className="wiki-search-empty">未找到匹配页面</p>
        ) : (
          <ul className="wiki-hit-list">
            {hits.map((hit) => (
              <li key={hit.page_id}>
                <button
                  type="button"
                  className={
                    hit.page_id === activePageId ? "wiki-hit-item active" : "wiki-hit-item"
                  }
                  onClick={() => onSelectPage(hit.page_id)}
                >
                  <span className="wiki-hit-title">{hit.title}</span>
                  {hit.snippets[0] ? (
                    <span className="wiki-hit-snippet">
                      {highlightPlainText(hit.snippets[0], highlightQuery)}
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="wiki-tree">
      {hubs.length === 0 ? (
        <p className="wiki-tree-empty">暂无目录</p>
      ) : (
        <ul className="wiki-hub-list">
          {indexPage ? (
            <li className="wiki-hub wiki-index-entry">
              <button
                type="button"
                className={
                  activePageId === "index" ? "wiki-page-item wiki-index-item active" : "wiki-page-item wiki-index-item"
                }
                onClick={() => onSelectPage("index")}
              >
                {indexPage.title}
              </button>
            </li>
          ) : null}
          {folderHubs.map((hub) => {
            const expanded = visibleExpanded.has(hub.name);
            return (
              <li key={hub.name} className="wiki-hub">
                <button
                  type="button"
                  className="wiki-hub-toggle"
                  aria-expanded={expanded}
                  onClick={() => toggleHub(hub.name)}
                >
                  <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
                  <span>{hub.name}</span>
                </button>
                {expanded ? (
                  <ul className="wiki-page-list">
                    {hub.pages.map((page) => (
                      <li key={page.page_id}>
                        <button
                          type="button"
                          className={
                            page.page_id === activePageId
                              ? "wiki-page-item active"
                              : "wiki-page-item"
                          }
                          onClick={() => onSelectPage(page.page_id)}
                        >
                          {page.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
