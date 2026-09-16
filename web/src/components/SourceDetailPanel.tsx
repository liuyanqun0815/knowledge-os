import { useState } from "react";
import { SourceChunksPanel } from "./SourceChunksPanel";
import { SourceClaimsPanel } from "./SourceClaimsPanel";

type SourceDetailPanelProps = {
  kbId: string;
  sourceId: string;
};

type DetailTab = "claims" | "chunks";

export function SourceDetailPanel({ kbId, sourceId }: SourceDetailPanelProps) {
  const [tab, setTab] = useState<DetailTab>("claims");

  return (
    <div className="source-detail-panel">
      <div className="source-detail-tabs" role="tablist" aria-label="文档详情">
        <button
          className={tab === "claims" ? "source-detail-tab is-active" : "source-detail-tab"}
          type="button"
          role="tab"
          aria-selected={tab === "claims"}
          onClick={() => setTab("claims")}
        >
          萃取 Claim
        </button>
        <button
          className={tab === "chunks" ? "source-detail-tab is-active" : "source-detail-tab"}
          type="button"
          role="tab"
          aria-selected={tab === "chunks"}
          onClick={() => setTab("chunks")}
        >
          切分 Chunk
        </button>
      </div>
      <div role="tabpanel">
        {tab === "claims" ? <SourceClaimsPanel kbId={kbId} sourceId={sourceId} /> : null}
        {tab === "chunks" ? <SourceChunksPanel kbId={kbId} sourceId={sourceId} /> : null}
      </div>
    </div>
  );
}
