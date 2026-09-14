import type { TraceChunkHit, TraceChunkItem } from "../api/types";

type TraceStepDetailProps = {
  node: string;
  detail: Record<string, unknown>;
};

function asChunkHits(value: unknown): TraceChunkHit[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is TraceChunkHit => typeof item === "object" && item !== null);
}

function asChunkItems(value: unknown): TraceChunkItem[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is TraceChunkItem => typeof item === "object" && item !== null && "chunk_id" in item);
}

function renderChunkHitTable(title: string, hits: TraceChunkHit[]) {
  if (hits.length === 0) {
    return null;
  }
  return (
    <div className="trace-detail-section">
      <h3>{title}</h3>
      <table className="trace-hit-table">
        <thead>
          <tr>
            <th>Chunk</th>
            <th>来源</th>
            <th>分数</th>
            <th>摘要</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((hit, index) => (
            <tr key={`${hit.chunk_id ?? "hit"}-${index}`}>
              <td>
                {hit.chunk_index !== undefined ? `#${hit.chunk_index + 1} ` : ""}
                {hit.title || hit.chunk_id?.slice(0, 8) || "—"}
              </td>
              <td>
                <code title={hit.source_id}>{hit.source_id ? hit.source_id.slice(0, 12) : "—"}</code>
              </td>
              <td>{hit.score !== undefined ? hit.score.toFixed(3) : "—"}</td>
              <td>{hit.snippet || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderChunkItems(title: string, chunks: TraceChunkItem[]) {
  if (chunks.length === 0) {
    return null;
  }
  return (
    <div className="trace-detail-section">
      <h3>{title}</h3>
      <ul className="trace-chunk-list">
        {chunks.map((chunk) => (
          <li key={chunk.chunk_id}>
            <strong>
              {chunk.chunk_index !== undefined ? `#${chunk.chunk_index + 1} ` : ""}
              {chunk.title || chunk.chunk_id.slice(0, 8)}
            </strong>
            {chunk.source_id ? (
              <span>
                {" "}
                · 来源 <code title={chunk.source_id}>{chunk.source_id.slice(0, 12)}</code>
              </span>
            ) : null}
            {chunk.status ? <span> · {chunk.status}</span> : null}
            {chunk.excerpt ? <p>{chunk.excerpt}</p> : null}
            <p className="chunk-id">
              <code title={chunk.chunk_id}>{chunk.chunk_id}</code>
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TraceStepDetail({ node, detail }: TraceStepDetailProps) {
  if (node === "retrieve") {
    const chunkHits = asChunkHits(detail.chunk_hit_items);
    const claimHits = asChunkHits(detail.claim_hit_items);
    const fusedHits = asChunkHits(detail.fused_hits).filter((hit) => hit.hit_type === "chunk" || hit.chunk_id);
    const displayHits = chunkHits.length > 0 ? chunkHits : fusedHits;
    return (
      <div className="trace-detail-panel">
        {renderChunkHitTable("命中 Chunk", displayHits)}
        {claimHits.length > 0 ? renderChunkHitTable("命中 Claim", claimHits) : null}
        <details className="trace-raw-detail">
          <summary>原始 JSON</summary>
          <pre>{JSON.stringify(detail, null, 2)}</pre>
        </details>
      </div>
    );
  }

  if (node === "verify" || node === "synthesize") {
    const chunks = asChunkItems(detail.chunks);
    const citations = asChunkHits(detail.citations).filter((item) => item.chunk_id);
    const chunkIds = Array.isArray(detail.chunk_ids)
      ? detail.chunk_ids.filter((item): item is string => typeof item === "string")
      : [];
    const chunkItems =
      chunks.length > 0
        ? chunks
        : chunkIds.map((chunkId) => ({ chunk_id: chunkId }) as TraceChunkItem);
    const citationItems: TraceChunkItem[] = citations.map((item) => ({
      chunk_id: item.chunk_id ?? "",
      source_id: item.source_id,
      excerpt: item.snippet,
    }));

    return (
      <div className="trace-detail-panel">
        {renderChunkItems(node === "verify" ? "核验 Chunk" : "引用 Chunk", chunkItems)}
        {node === "synthesize" && citationItems.length > 0 ? renderChunkItems("综合引用", citationItems) : null}
        <details className="trace-raw-detail">
          <summary>原始 JSON</summary>
          <pre>{JSON.stringify(detail, null, 2)}</pre>
        </details>
      </div>
    );
  }

  return <pre>{JSON.stringify(detail, null, 2)}</pre>;
}
