import { type ChangeEvent, type DragEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { listSources, uploadSource } from "../api/sources";
import type { SourceItem, SourceUploadResponse } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { SourceFileBrowser } from "../components/SourceFileBrowser";

const ACCEPTED_EXTENSIONS = [".md", ".txt", ".zip"];

function isAcceptedUploadFile(file: File): boolean {
  const lowerName = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((suffix) => lowerName.endsWith(suffix));
}

function formatUploadSummary(result: SourceUploadResponse): string {
  if (result.upload_mode === "zip") {
    return `ZIP 解压完成：成功 ${result.files_ingested} 个，跳过 ${result.files_skipped} 个。`;
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
  const [replacesSourceId, setReplacesSourceId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(null);
  const [uploadSummary, setUploadSummary] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const isZipSelected = selectedFile?.name.toLowerCase().endsWith(".zip") ?? false;

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
    setSources([]);
    setSelectedFile(null);
    setReplacesSourceId("");
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

  function selectFile(file: File | undefined) {
    if (!file) {
      return;
    }
    if (!isAcceptedUploadFile(file)) {
      setError("仅支持 .md、.txt 或 .zip 文件。");
      return;
    }
    setSelectedFile(file);
    setUploadSummary(null);
    setError(null);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    selectFile(event.dataTransfer.files[0]);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!kbId || !selectedFile) {
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadSummary(null);
    const trimmedReplacesId = replacesSourceId.trim();
    const uploadOptions = trimmedReplacesId && !isZipSelected ? { replacesSourceId: trimmedReplacesId } : {};
    try {
      const result = await uploadSource(kbId, selectedFile, uploadOptions);
      setSelectedFile(null);
      setReplacesSourceId("");
      setUploadSummary(formatUploadSummary(result));
      await loadSources();
    } catch {
      setError("文档上传失败，请稍后重试。");
    } finally {
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
          <p>支持 .md / .txt 单文件或 .zip 压缩包（保留目录结构）上传。</p>
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
          <label htmlFor="source-file">选择文档 (.md / .txt / .zip)</label>
          <input
            id="source-file"
            type="file"
            accept=".md,.txt,.zip,text/markdown,text/plain,application/zip"
            onChange={handleFileChange}
            disabled={isUploading}
          />
          <p>可点击选择、或将文件拖放到此处。ZIP 内仅解压 .md / .txt，并保留目录结构。</p>
          {selectedFile ? <p>已选择：{selectedFile.name}</p> : null}
        </div>
        <label htmlFor="replaces-source-id">替换文档 ID (replaces_source_id)</label>
        <input
          id="replaces-source-id"
          type="text"
          value={replacesSourceId}
          onChange={(event) => setReplacesSourceId(event.target.value)}
          placeholder="可选：单文件上传时填写被替换的 source_id"
          disabled={isUploading || isZipSelected}
        />
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={!selectedFile || isUploading}>
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
        />
      ) : null}
    </section>
  );
}
