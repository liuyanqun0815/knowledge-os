import { type ChangeEvent, type DragEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { listSources, uploadSource, uploadTree, type UploadTreeEntry } from "../api/sources";
import type { SourceItem, SourceUploadResponse } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { SourceFileBrowser } from "../components/SourceFileBrowser";

const ACCEPTED_EXTENSIONS = [".md", ".txt", ".pdf", ".docx", ".doc", ".zip"];

function isAcceptedUploadFile(file: File): boolean {
  const lowerName = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((suffix) => lowerName.endsWith(suffix));
}

function formatUploadSummary(result: SourceUploadResponse): string {
  if (result.upload_mode === "zip") {
    return `ZIP 解压完成：成功 ${result.files_ingested} 个，跳过 ${result.files_skipped} 个。`;
  }
  if (result.upload_mode === "tree") {
    return `文件夹上传完成：成功 ${result.files_ingested} 个，跳过 ${result.files_skipped} 个。`;
  }

  const item = result.results[0];
  if (!item) {
    return "上传成功。";
  }

  return `上传成功：新建 Claim ${item.claims_created} 条，隔离 ${item.quarantined} 条。`;
}

export function SourcesPage() {
  const { kbId } = useKb();
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedTreeEntries, setSelectedTreeEntries] = useState<UploadTreeEntry[]>([]);
  const [replacesSourceId, setReplacesSourceId] = useState("");
  const [subjectBindMode, setSubjectBindMode] = useState<"auto" | "on" | "off">("auto");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(null);
  const [uploadSummary, setUploadSummary] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);
  const pollGenerationRef = useRef(0);

  const hasSelectedUpload = selectedFile !== null || selectedTreeEntries.length > 0;
  const isZipSelected = Boolean(selectedFile?.name.toLowerCase().endsWith(".zip"));
  const canReplaceHistorical =
    selectedFile !== null && !isZipSelected && selectedTreeEntries.length === 0;
  const replaceCandidates = sources.filter((item) =>
    ["succeeded", "succeeded_partial", "ready"].includes(item.compile_status),
  );

  const loadSources = useCallback(async () => {
    if (!kbId) {
      return;
    }

    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    setIsLoading(true);
    try {
      const items = await listSources(kbId, { query: searchQuery });
      if (requestSequence.current === requestId) {
        setSources(items);
        setError(null);
      }
    } catch {
      if (requestSequence.current === requestId) {
        setError("文档列表加载失败，请稍后重试。");
      }
    } finally {
      if (requestSequence.current === requestId) {
        setIsLoading(false);
      }
    }
  }, [kbId, searchQuery]);

  useEffect(() => {
    requestSequence.current += 1;
    pollGenerationRef.current += 1;
    setSources([]);
    setSelectedFile(null);
    setSelectedTreeEntries([]);
    setReplacesSourceId("");
    setSubjectBindMode("auto");
    setUploadSummary(null);
    setExpandedSourceId(null);
    setSearchQuery("");
    setError(null);
  }, [kbId]);

  useEffect(() => {
    if (!kbId) {
      return;
    }
    const timer = window.setTimeout(() => {
      void loadSources();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [kbId, loadSources]);

  useEffect(() => {
    return () => {
      pollGenerationRef.current += 1;
    };
  }, []);

  function selectFile(file: File | undefined) {
    if (!file) {
      return;
    }
    if (!isAcceptedUploadFile(file)) {
      setError("仅支持 .md、.txt、.pdf、.docx、.doc 或 .zip 文件。");
      return;
    }
    setSelectedFile(file);
    setSelectedTreeEntries([]);
    setReplacesSourceId("");
    setUploadSummary(null);
    setError(null);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0]);
  }

  function handleFolderChange(event: ChangeEvent<HTMLInputElement>) {
    const entries = [...(event.target.files ?? [])]
      .filter((file) =>
        [".md", ".txt", ".pdf", ".docx", ".doc"].some((suffix) => file.name.toLowerCase().endsWith(suffix)),
      )
      .map((file) => ({ file, relativePath: file.webkitRelativePath || file.name }));
    if (entries.length === 0) {
      setError("所选文件夹中没有可上传的 .md / .txt / .pdf / .docx / .doc 文件。");
      return;
    }
    setSelectedFile(null);
    setSelectedTreeEntries(entries);
    setReplacesSourceId("");
    setUploadSummary(null);
    setError(null);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    selectFile(event.dataTransfer.files[0]);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!kbId || !hasSelectedUpload) {
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadSummary(null);
    const pollKbId = kbId;
    const pollQuery = searchQuery;
    try {
      const result =
        selectedTreeEntries.length > 0
          ? await uploadTree(kbId, selectedTreeEntries, { subjectBindMode })
          : await uploadSource(kbId, selectedFile as File, {
              ...(canReplaceHistorical && replacesSourceId ? { replacesSourceId } : {}),
              subjectBindMode,
            });
      setSelectedFile(null);
      setSelectedTreeEntries([]);
      setReplacesSourceId("");
      setSubjectBindMode("auto");
      setUploadSummary(
        result.accepted_async !== false
          ? `已接收 ${result.results.length} 个文件，后台编译中`
          : formatUploadSummary(result),
      );
      setIsUploading(false);
      const pollGen = ++pollGenerationRef.current;
      void (async () => {
        const deadline = Date.now() + 180_000;
        while (Date.now() < deadline && pollGenerationRef.current === pollGen) {
          const items = await listSources(pollKbId, { query: pollQuery });
          if (pollGenerationRef.current !== pollGen) {
            return;
          }
          setSources(items);
          const busy = items.some(
            (s) =>
              s.compile_status === "pending" ||
              s.compile_status === "running" ||
              s.compile_status === "enriching",
          );
          if (!busy) return;
          await new Promise((r) => setTimeout(r, 2000));
        }
      })();
    } catch {
      setError("文档上传失败，请稍后重试。");
      setIsUploading(false);
    }
  }

  function toggleSource(sourceId: string) {
    setExpandedSourceId((current) => (current === sourceId ? null : sourceId));
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可上传和管理文档。" />;
  }

  return (
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>文档来源</h1>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {uploadSummary ? (
        <p className="success-banner" role="status">
          {uploadSummary}
        </p>
      ) : null}

      <form className="form-card" onSubmit={handleUpload}>
        <div
          className="upload-drop-zone"
          data-testid="source-drop-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <p className="upload-drop-title">选择文档</p>
          <p>拖拽文件到此处，或选择 .md / .txt / .pdf / .docx / .doc / .zip；选择文件夹可保留目录结构。</p>
          <div className="upload-picker-actions">
            <label className="button button-secondary" htmlFor="source-file">
              选择文件
            </label>
            <label className="button button-secondary" htmlFor="source-folder">
              选择文件夹
            </label>
          </div>
          <input
            id="source-file"
            className="visually-hidden"
            type="file"
            accept=".md,.txt,.pdf,.docx,.doc,.zip,text/markdown,text/plain,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/zip"
            aria-label="选择文档"
            onChange={handleFileChange}
            disabled={isUploading}
          />
          <input
            id="source-folder"
            className="visually-hidden"
            type="file"
            accept=".md,.txt,.pdf,.docx,.doc,text/markdown,text/plain,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            multiple
            aria-label="选择文件夹"
            {...{ webkitdirectory: "", directory: "" }}
            onChange={handleFolderChange}
            disabled={isUploading}
          />
          {selectedFile ? <p>已选择：{selectedFile.name}</p> : null}
          {selectedTreeEntries.length > 0 ? <p>已选择文件夹：{selectedTreeEntries.length} 个文档</p> : null}
        </div>
        <label htmlFor="replaces-source-id">替换历史文档</label>
        <select
          id="replaces-source-id"
          value={canReplaceHistorical ? replacesSourceId : ""}
          onChange={(event) => setReplacesSourceId(event.target.value)}
          disabled={isUploading || !canReplaceHistorical}
        >
          <option value="">
            可选：用新文件替换已有文档，将自动 Diff 并 supersede 相关 Claim
          </option>
          {replaceCandidates.map((item) => (
            <option key={item.id} value={item.id}>
              {item.relative_path || item.filename}
            </option>
          ))}
        </select>
        {!canReplaceHistorical && hasSelectedUpload ? (
          <p className="form-helper">仅单文件（非 ZIP）支持替换历史文档并触发 Claim 演化。</p>
        ) : null}
        <label htmlFor="subject-bind-mode">主体绑定产品</label>
        <select
          id="subject-bind-mode"
          value={subjectBindMode}
          onChange={(event) => setSubjectBindMode(event.target.value as "auto" | "on" | "off")}
          disabled={isUploading}
        >
          <option value="auto">自动（推荐）</option>
          <option value="on">强制绑定</option>
          <option value="off">关闭</option>
        </select>
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={!hasSelectedUpload || isUploading}>
            {isUploading ? "上传中…" : "上传"}
          </button>
        </div>
      </form>

      {isLoading ? <p role="status">正在加载文档…</p> : null}
      {!isLoading && !error && sources.length === 0 && !searchQuery ? (
        <EmptyState title="暂无文档" description="上传第一个文档开始构建知识库。" />
      ) : null}
      {!isLoading ? (
        <SourceFileBrowser
          kbId={kbId}
          sources={sources}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          expandedSourceId={expandedSourceId}
          onToggleSource={toggleSource}
          onChanged={loadSources}
          onError={setError}
        />
      ) : null}
    </section>
  );
}
