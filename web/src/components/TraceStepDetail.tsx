import type { TraceChunkHit, TraceChunkItem } from "../api/types";

type TraceStepDetailProps = {
  node: string;
  detail: Record<string, unknown>;
};

type HitTableOptions = {
  scoreLabel?: string;
  scoreHint?: string;
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

function hitIdentity(hit: TraceChunkHit): string {
  if (hit.hit_type === "claim" || hit.claim_id) {
    return hit.claim_id ? `Claim ${hit.claim_id.slice(0, 8)}` : "Claim";
  }
  if (hit.hit_type === "wiki" || hit.ref_id || hit.path) {
    return hit.title || hit.ref_id || hit.path || "Wiki";
  }
  const index = hit.chunk_index !== undefined ? `#${hit.chunk_index + 1} ` : "";
  return `${index}${hit.title || hit.chunk_id?.slice(0, 8) || "Chunk"}`;
}

function hitSource(hit: TraceChunkHit): string {
  if (hit.source_id) {
    return hit.source_id.slice(0, 12);
  }
  if (hit.path) {
    return hit.path;
  }
  if (hit.ref_id) {
    return hit.ref_id;
  }
  return "—";
}

function renderChunkHitTable(title: string, hits: TraceChunkHit[], options: HitTableOptions = {}) {
  if (hits.length === 0) {
    return null;
  }
  const scoreLabel = options.scoreLabel ?? "分数";
  return (
    <div className="trace-detail-section">
      <h3>{title}</h3>
      {options.scoreHint ? <p className="trace-score-hint">{options.scoreHint}</p> : null}
      <table className="trace-hit-table">
        <thead>
          <tr>
            <th>命中</th>
            <th>来源</th>
            <th title={options.scoreHint}>{scoreLabel}</th>
            <th>摘要</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((hit, index) => (
            <tr key={`${hit.chunk_id ?? hit.claim_id ?? hit.ref_id ?? "hit"}-${index}`}>
              <td>{hitIdentity(hit)}</td>
              <td>
                <code title={hit.source_id || hit.path || hit.ref_id}>{hitSource(hit)}</code>
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
  if (node === "normalize") {
    const input = typeof detail.input === "string" ? detail.input : "";
    const output = typeof detail.output === "string" ? detail.output : "";
    const changed = detail.changed === true;
    const replacements = Array.isArray(detail.replacements)
      ? detail.replacements.filter(
          (item): item is { from: string; to: string } =>
            typeof item === "object" &&
            item !== null &&
            typeof (item as { from?: unknown }).from === "string" &&
            typeof (item as { to?: unknown }).to === "string",
        )
      : [];
    return (
      <div className="trace-detail-panel">
        <div className="trace-detail-section">
          <h3>输入</h3>
          <p className="trace-io-text">{input || "—"}</p>
        </div>
        <div className="trace-detail-section">
          <h3>输出{changed ? "" : "（未变化）"}</h3>
          <p className="trace-io-text">{output || "—"}</p>
        </div>
        {replacements.length > 0 ? (
          <div className="trace-detail-section">
            <h3>替换</h3>
            <ul className="trace-replacement-list">
              {replacements.map((item, index) => (
                <li key={`${item.from}-${item.to}-${index}`}>
                  <code>{item.from}</code>
                  <span> → </span>
                  <code>{item.to}</code>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <details className="trace-raw-detail">
          <summary>原始 JSON</summary>
          <pre>{JSON.stringify(detail, null, 2)}</pre>
        </details>
      </div>
    );
  }

  if (node === "recall") {
    const episodes = Array.isArray(detail.episodes) ? detail.episodes : [];
    const sessionId = typeof detail.session_id === "string" ? detail.session_id : null;
    return (
      <div className="trace-detail-panel">
        <div className="trace-detail-section">
          <h3>历史会话</h3>
          {sessionId ? (
            <p className="trace-score-hint">
              session <code>{sessionId}</code>
            </p>
          ) : (
            <p className="trace-score-hint">未绑定 session</p>
          )}
          {episodes.length === 0 ? (
            <p className="empty-copy">暂无历史会话</p>
          ) : (
            <ol className="trace-episode-list">
              {episodes.map((episode, index) => {
                const item =
                  typeof episode === "object" && episode !== null
                    ? (episode as Record<string, unknown>)
                    : {};
                const question = typeof item.q === "string" ? item.q : typeof item.question === "string" ? item.question : "";
                const answer = typeof item.a === "string" ? item.a : typeof item.answer === "string" ? item.answer : "";
                return (
                  <li key={`episode-${index}`}>
                    <p>
                      <strong>Q：</strong>
                      {question || "—"}
                    </p>
                    <p>
                      <strong>A：</strong>
                      {answer || "—"}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
        <details className="trace-raw-detail">
          <summary>原始 JSON</summary>
          <pre>{JSON.stringify(detail, null, 2)}</pre>
        </details>
      </div>
    );
  }

  if (node === "retrieve") {
    const chunkHits = asChunkHits(detail.chunk_hit_items);
    const claimHits = asChunkHits(detail.claim_hit_items);
    const wikiHits = asChunkHits(detail.wiki_hit_items);
    const fusedHits = asChunkHits(detail.fused_hits);
    const timingKeys = [
      ["embed_ms", "Embed"],
      ["claim_ms", "Claim"],
      ["chunk_ms", "Chunk"],
      ["wiki_ms", "Wiki"],
      ["fuse_ms", "融合"],
    ] as const;
    const timings = timingKeys
      .map(([key, label]) => {
        const value = detail[key];
        return typeof value === "number" ? { key, label, value } : null;
      })
      .filter((item): item is { key: string; label: string; value: number } => item !== null);
    return (
      <div className="trace-detail-panel">
        {timings.length > 0 ? (
          <div className="trace-detail-section">
            <h3>分阶段耗时</h3>
            <ul className="trace-timing-list">
              {timings.map((item) => (
                <li key={item.key}>
                  <span>{item.label}</span>
                  <strong>{item.value} ms</strong>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {renderChunkHitTable("命中 Claim", claimHits, { scoreLabel: "检索分" })}
        {renderChunkHitTable("命中 Wiki", wikiHits, { scoreLabel: "检索分" })}
        {renderChunkHitTable("命中 Chunk", chunkHits, { scoreLabel: "检索分" })}
        {renderChunkHitTable("融合结果 (RRF)", fusedHits, {
          scoreLabel: "融合分",
          scoreHint: "加权 RRF：weight / (60 + 名次)，约 0.01x，只比相对高低",
        })}
        <details className="trace-raw-detail">
          <summary>原始 JSON</summary>
          <pre>{JSON.stringify(detail, null, 2)}</pre>
        </details>
      </div>
    );
  }

  if (node === "rerank") {
    const inputHits = asChunkHits(detail.input_hits);
    const outputHits = asChunkHits(detail.output_hits);
    return (
      <div className="trace-detail-panel">
        {renderChunkHitTable("重排前", inputHits, {
          scoreLabel: "融合分",
          scoreHint: "加权 RRF：weight / (60 + 名次)，约 0.01x，只比相对高低",
        })}
        {renderChunkHitTable("重排后", outputHits, {
          scoreLabel: "相关性分",
          scoreHint: "Cross-encoder 重排分（通常更接近 0–1）",
        })}
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
