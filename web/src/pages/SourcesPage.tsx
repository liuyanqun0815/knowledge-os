import { type ChangeEvent, type DragEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { listSources, uploadSource } from "../api/sources";
import type { SourceItem } from "../api/types";
import { useKb } from "../app/KbContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";

const STATUS_LABELS: Record<SourceItem["compile_status"], string> = {
  pending: "等待编译",
  running: "编译中",
  succeeded: "已完成",
  failed: "编译失败",
};

export function SourcesPage() {
  const { kbId } = useKb();
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [replacesSourceId, setReplacesSourceId] = useState("");
  const [uploadSummary, setUploadSummary] = useState<{ claims_created: number; quarantined: number } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const loadSources = useCallback(async () => {
    if (!kbId) {
      return;
    }

    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    try {
      const items = await listSources(kbId);
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
  }, [kbId]);

  useEffect(() => {
    requestSequence.current += 1;
    setSources([]);
    setSelectedFile(null);
    setReplacesSourceId("");
    setUploadSummary(null);
    setError(null);
    if (!kbId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    void loadSources();
  }, [kbId, loadSources]);

  const hasCompilingSource = sources.some(({ compile_status }) =>
    ["pending", "running"].includes(compile_status),
  );

  useEffect(() => {
    if (!kbId || !hasCompilingSource) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadSources();
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, [hasCompilingSource, kbId, loadSources]);

  function selectFile(file: File | undefined) {
    if (file) {
      setSelectedFile(file);
      setUploadSummary(null);
      setError(null);
    }
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
    const uploadOptions = trimmedReplacesId ? { replacesSourceId: trimmedReplacesId } : {};
    try {
      const result = await uploadSource(kbId, selectedFile, uploadOptions);
      setSelectedFile(null);
      setReplacesSourceId("");
      setUploadSummary({ claims_created: result.claims_created, quarantined: result.quarantined });
      await loadSources();
    } catch {
      setError("文档上传失败，请稍后重试。");
    } finally {
      setIsUploading(false);
    }
  }

  if (!kbId) {
    return <EmptyState title="请先选择知识库" description="选择知识库后即可上传和管理文档。" />;
  }

  return (
    <section className="page-section">
      <div className="page-header">
        <div>
          <h1>文档来源</h1>
          <p>上传文档并查看知识编译状态。</p>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {uploadSummary ? (
        <p className="success-banner" role="status">
          上传成功：新建 Claim {uploadSummary.claims_created} 条，隔离 {uploadSummary.quarantined} 条。
        </p>
      ) : null}

      <form className="form-card" onSubmit={handleUpload}>
        <div
          className="upload-drop-zone"
          data-testid="source-drop-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <label htmlFor="source-file">选择文档</label>
          <input id="source-file" type="file" onChange={handleFileChange} disabled={isUploading} />
          <p>可点击选择或将文件拖放到此处。</p>
          {selectedFile ? <p>已选择：{selectedFile.name}</p> : null}
        </div>
        <label htmlFor="replaces-source-id">替换文档 ID (replaces_source_id)</label>
        <input
          id="replaces-source-id"
          type="text"
          value={replacesSourceId}
          onChange={(event) => setReplacesSourceId(event.target.value)}
          placeholder="可选：填写被替换的 source_id 以触发文档演化"
          disabled={isUploading}
        />
        <button className="button button-primary" type="submit" disabled={!selectedFile || isUploading}>
          {isUploading ? "上传中…" : "上传文档"}
        </button>
      </form>

      {isLoading ? <p role="status">正在加载文档…</p> : null}
      {!isLoading && !error && sources.length === 0 ? (
        <EmptyState title="暂无文档" description="上传第一个文档开始构建知识库。" />
      ) : null}
      {sources.length > 0 ? (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>文件名</th>
                <th>编译状态</th>
                <th>上传时间</th>
                <th>错误摘要</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.id}>
                  <td>{source.filename}</td>
                  <td>{STATUS_LABELS[source.compile_status]}</td>
                  <td>{source.created_at ? new Date(source.created_at).toLocaleString() : "—"}</td>
                  <td>{source.error_summary || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
