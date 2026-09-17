import { useEffect, useState } from "react";
import { fetchSourceChunks } from "../api/sources";
import type { SourceChunkItem } from "../api/types";

type SourceChunksPanelProps = {
  kbId: string;
  sourceId: string;
};

const STATUS_LABELS: Record<string, string> = {
  active: "生效",
  stale: "已过期",
};

export function SourceChunksPanel({ kbId, sourceId }: SourceChunksPanelProps) {
  const [chunks, setChunks] = useState<SourceChunkItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    fetchSourceChunks(kbId, sourceId, "all")
      .then((items) => {
        if (active) {
          setChunks(items);
        }
      })
      .catch(() => {
        if (active) {
          setError("切分段落加载失败。");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [kbId, sourceId]);

  if (isLoading) {
    return <p className="form-helper">正在加载切分段落…</p>;
  }

  if (error) {
    return <p className="form-helper">{error}</p>;
  }

  if (chunks.length === 0) {
    return (
      <p className="form-helper">
        该文档没有 Chunk 记录。上传流程会在萃取 Claim 之后切分；若二次 LLM 切分失败，也可能只留下已过期段。
      </p>
    );
  }

  const activeCount = chunks.filter((chunk) => chunk.status === "active").length;

  return (
    <div className="chunks-panel">
      <p className="form-helper">
        共 {chunks.length} 段（生效 {activeCount}）
        {activeCount === 0
          ? "。当前全部为已过期，Ask 检索不会使用它们；可重新上传该文件以再切分。"
          : null}
      </p>
      <div className="chunks-list">
        {chunks.map((chunk) => (
          <details key={chunk.id} className="chunk-item">
            <summary>
              <span className="chunk-item-title">
                #{chunk.chunk_index + 1} {chunk.title || `段落 ${chunk.chunk_index + 1}`}
              </span>
              <span className="chunk-item-meta">
                {STATUS_LABELS[chunk.status] ?? chunk.status} · {chunk.token_count} tokens · {chunk.start}-{chunk.end}
              </span>
            </summary>
            <div className="chunk-item-body">
              {chunk.summary ? <p className="chunk-summary">{chunk.summary}</p> : null}
              {chunk.topics.length > 0 ? (
                <p className="chunk-topics">主题：{chunk.topics.join("、")}</p>
              ) : null}
              {chunk.section_path.length > 0 ? (
                <p className="chunk-topics">路径：{chunk.section_path.join(" / ")}</p>
              ) : null}
              <p className="chunk-id">
                <code title={chunk.id}>{chunk.id.slice(0, 8)}…</code>
              </p>
              <pre>{chunk.text}</pre>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
