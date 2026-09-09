import { Fragment, type ChangeEvent, useMemo, useState } from "react";
import type { SourceItem } from "../api/types";
import { SourceClaimsPanel } from "./SourceClaimsPanel";

const STATUS_LABELS: Record<SourceItem["compile_status"], string> = {
  pending: "等待编译",
  running: "编译中",
  succeeded: "已完成",
  failed: "编译失败",
};

type SourceFileBrowserProps = {
  kbId: string;
  sources: SourceItem[];
  searchQuery: string;
  onSearchChange: (value: string) => void;
  expandedSourceId: string | null;
  onToggleSource: (sourceId: string) => void;
};

export function SourceFileBrowser({
  kbId,
  sources,
  searchQuery,
  onSearchChange,
  expandedSourceId,
  onToggleSource,
}: SourceFileBrowserProps) {
  const grouped = useMemo(() => {
    const groups = new Map<string, SourceItem[]>();
    for (const source of sources) {
      const directory = source.directory || "/";
      const bucket = groups.get(directory) ?? [];
      bucket.push(source);
      groups.set(directory, bucket);
    }
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
  }, [sources]);

  function handleSearchChange(event: ChangeEvent<HTMLInputElement>) {
    onSearchChange(event.target.value);
  }

  if (sources.length === 0) {
    return (
      <div className="table-card">
        <label htmlFor="source-search">模糊搜索</label>
        <input
          id="source-search"
          type="search"
          value={searchQuery}
          onChange={handleSearchChange}
          placeholder="按文件名、目录或 source_id 搜索"
        />
        <p className="form-helper">未找到匹配的文档。</p>
      </div>
    );
  }

  return (
    <div className="table-card">
      <label htmlFor="source-search">模糊搜索</label>
      <input
        id="source-search"
        type="search"
        value={searchQuery}
        onChange={handleSearchChange}
        placeholder="按文件名、目录或 source_id 搜索"
      />
      <table>
        <thead>
          <tr>
            <th>目录</th>
            <th>相对路径</th>
            <th>Source ID</th>
            <th>Claim 数</th>
            <th>状态</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {grouped.map(([directory, items]) =>
            items.map((source) => (
              <Fragment key={source.id}>
                <tr>
                  <td>{directory}</td>
                  <td>{source.relative_path || source.filename}</td>
                  <td>{source.id}</td>
                  <td>{source.claims_count ?? 0}</td>
                  <td>{STATUS_LABELS[source.compile_status]}</td>
                  <td>{source.created_at ? new Date(source.created_at).toLocaleString() : "—"}</td>
                  <td>
                    <button className="button button-secondary" type="button" onClick={() => onToggleSource(source.id)}>
                      {expandedSourceId === source.id ? "收起萃取" : "查看萃取"}
                    </button>
                  </td>
                </tr>
                {expandedSourceId === source.id ? (
                  <tr>
                    <td colSpan={7}>
                      <SourceClaimsPanel kbId={kbId} sourceId={source.id} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}
