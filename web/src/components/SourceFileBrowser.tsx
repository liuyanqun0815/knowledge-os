import { Fragment, type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { deleteSource, deleteTree, fetchSourceContent, moveSources } from "../api/sources";
import type { SourceItem } from "../api/types";
import { SourceDetailPanel } from "./SourceDetailPanel";
import { SourceContentModal } from "./SourceContentModal";

const STATUS_LABELS: Record<string, string> = {
  pending: "等待编译",
  running: "编译中",
  enriching: "LLM 补抽中",
  ready: "已完成",
  succeeded: "已完成",
  succeeded_partial: "部分完成",
  failed: "编译失败",
};

type SourceFileBrowserProps = {
  kbId: string;
  sources: SourceItem[];
  searchQuery: string;
  onSearchChange: (value: string) => void;
  expandedSourceId: string | null;
  onToggleSource: (sourceId: string) => void;
  onChanged: () => void | Promise<void>;
  onError: (message: string) => void;
};

type FolderNode = {
  name: string;
  path: string;
  folders: Map<string, FolderNode>;
  files: SourceItem[];
  documentCount: number;
};

type PreviewState = {
  sourceId: string;
  title: string;
  content: string | null;
  isLoading: boolean;
  error: string | null;
};

function createFolder(name = "", path = ""): FolderNode {
  return { name, path, folders: new Map(), files: [], documentCount: 0 };
}

function buildTree(sources: SourceItem[]): FolderNode {
  const root = createFolder();
  for (const source of sources) {
    const parts = (source.relative_path || source.filename).split("/").filter(Boolean);
    let folder = root;
    folder.documentCount += 1;
    for (const part of parts.slice(0, -1)) {
      const path = folder.path ? `${folder.path}/${part}` : part;
      if (!folder.folders.has(part)) {
        folder.folders.set(part, createFolder(part, path));
      }
      folder = folder.folders.get(part) as FolderNode;
      folder.documentCount += 1;
    }
    folder.files.push(source);
  }
  return root;
}

function folderPaths(folder: FolderNode): string[] {
  return [...folder.folders.values()].flatMap((child) => [child.path, ...folderPaths(child)]);
}

export function SourceFileBrowser({
  kbId,
  sources,
  searchQuery,
  onSearchChange,
  expandedSourceId,
  onToggleSource,
  onChanged,
  onError,
}: SourceFileBrowserProps) {
  const tree = useMemo(() => buildTree(sources), [sources]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(() => new Set());
  const [preview, setPreview] = useState<PreviewState | null>(null);

  useEffect(() => {
    const validPaths = new Set(folderPaths(tree));
    setExpandedFolders((current) => new Set([...current].filter((path) => validPaths.has(path))));
  }, [tree]);

  const closePreview = useCallback(() => {
    setPreview(null);
  }, []);

  function handleSearchChange(event: ChangeEvent<HTMLInputElement>) {
    onSearchChange(event.target.value);
  }

  function toggleFolder(path: string) {
    setExpandedFolders((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  async function openPreview(source: SourceItem) {
    const title = source.relative_path || source.filename;
    setPreview({
      sourceId: source.id,
      title,
      content: null,
      isLoading: true,
      error: null,
    });
    try {
      const payload = await fetchSourceContent(kbId, source.id);
      setPreview({
        sourceId: source.id,
        title: payload.relative_path || payload.title,
        content: payload.content,
        isLoading: false,
        error: null,
      });
    } catch {
      setPreview({
        sourceId: source.id,
        title,
        content: null,
        isLoading: false,
        error: "原文加载失败，文件可能过大或不存在。",
      });
    }
  }

  async function handleMove(path: string, isFolder: boolean) {
    const sourcePath = isFolder ? `${path}/` : path;
    const destination = window.prompt("请输入目标相对路径", sourcePath);
    if (!destination || destination === sourcePath) {
      return;
    }
    try {
      await moveSources(kbId, sourcePath, destination);
      await onChanged();
    } catch {
      onError("移动失败，请检查目标路径是否冲突。");
    }
  }

  async function handleDeleteFile(source: SourceItem) {
    const path = source.relative_path || source.filename;
    if (!window.confirm(`确认删除文件 ${path}？`)) {
      return;
    }
    try {
      await deleteSource(kbId, source.id);
      await onChanged();
    } catch {
      onError("删除文件失败，请稍后重试。");
    }
  }

  async function handleDeleteFolder(folder: FolderNode) {
    if (!window.confirm(`确认删除文件夹 ${folder.name}（共 ${folder.documentCount} 个文档）？`)) {
      return;
    }
    try {
      await deleteTree(kbId, `${folder.path}/`);
      await onChanged();
    } catch {
      onError("删除文件夹失败，请稍后重试。");
    }
  }

  function renderFile(source: SourceItem, depth: number) {
    const path = source.relative_path || source.filename;
    return (
      <Fragment key={source.id}>
        <div className="source-tree-row source-tree-file" style={{ paddingInlineStart: `${depth * 1.5 + 0.75}rem` }}>
          <button
            type="button"
            className="source-tree-name source-tree-file-link"
            onClick={() => void openPreview(source)}
          >
            📄 {source.filename}
          </button>
          <div className="source-tree-meta">
            <span className="source-tree-stat">{source.claims_count ?? 0} 条 Claim</span>
            <span className="source-tree-stat">{STATUS_LABELS[source.compile_status]}</span>
            <div className="source-tree-actions">
              <button
                aria-label={`查看文件 ${source.filename}`}
                className="button button-secondary"
                type="button"
                onClick={() => void openPreview(source)}
              >
                查看
              </button>
              <button className="button button-secondary" type="button" onClick={() => onToggleSource(source.id)}>
                {expandedSourceId === source.id ? "收起萃取" : "查看萃取"}
              </button>
              <button
                aria-label={`移动文件 ${source.filename}`}
                className="button button-secondary"
                type="button"
                onClick={() => void handleMove(path, false)}
              >
                移动
              </button>
              <button
                aria-label={`删除文件 ${source.filename}`}
                className="button button-danger"
                type="button"
                onClick={() => void handleDeleteFile(source)}
              >
                删除
              </button>
            </div>
          </div>
        </div>
        {expandedSourceId === source.id ? (
          <div className="source-tree-claims" style={{ marginInlineStart: `${depth * 1.5 + 2.25}rem` }}>
            <SourceDetailPanel kbId={kbId} sourceId={source.id} />
          </div>
        ) : null}
      </Fragment>
    );
  }

  function renderFolder(folder: FolderNode, depth: number) {
    const isExpanded = expandedFolders.has(folder.path);
    const children = [...folder.folders.values()].sort((left, right) => left.name.localeCompare(right.name));
    const files = [...folder.files].sort((left, right) => left.filename.localeCompare(right.filename));
    return (
      <div key={folder.path} role="treeitem" aria-expanded={isExpanded}>
        <div className="source-tree-row source-tree-folder" style={{ paddingInlineStart: `${depth * 1.5 + 0.75}rem` }}>
          <button
            aria-label={`${isExpanded ? "收起" : "展开"}文件夹 ${folder.name}`}
            className="source-tree-toggle"
            type="button"
            onClick={() => toggleFolder(folder.path)}
          >
            {isExpanded ? "▾" : "▸"} 📁 {folder.name}
          </button>
          <div className="source-tree-meta">
            <span className="source-tree-stat">{folder.documentCount} 个文档</span>
            <div className="source-tree-actions">
              <button
                aria-label={`移动文件夹 ${folder.name}`}
                className="button button-secondary"
                type="button"
                onClick={() => void handleMove(folder.path, true)}
              >
                移动
              </button>
              <button
                aria-label={`删除文件夹 ${folder.name}`}
                className="button button-danger"
                type="button"
                onClick={() => void handleDeleteFolder(folder)}
              >
                删除
              </button>
            </div>
          </div>
        </div>
        {isExpanded ? (
          <div role="group">
            {children.map((child) => renderFolder(child, depth + 1))}
            {files.map((source) => renderFile(source, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <>
      <div className="table-card source-browser-card">
        <div className="source-search-bar">
          <label htmlFor="source-search">模糊搜索</label>
          <input
            id="source-search"
            type="search"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="文件名、目录或 ID"
          />
        </div>
        {sources.length === 0 ? (
          <p className="form-helper source-browser-empty">未找到匹配的文档。</p>
        ) : (
          <div className="source-tree" role="tree" aria-label="文档目录树">
            {[...tree.folders.values()]
              .sort((left, right) => left.name.localeCompare(right.name))
              .map((folder) => renderFolder(folder, 0))}
            {[...tree.files]
              .sort((left, right) => left.filename.localeCompare(right.filename))
              .map((source) => renderFile(source, 0))}
          </div>
        )}
      </div>
      {preview ? (
        <SourceContentModal
          title={preview.title}
          content={preview.content}
          isLoading={preview.isLoading}
          error={preview.error}
          onClose={closePreview}
        />
      ) : null}
    </>
  );
}
