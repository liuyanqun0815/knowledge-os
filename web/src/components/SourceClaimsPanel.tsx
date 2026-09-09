import { useEffect, useState } from "react";
import { fetchSourceClaims } from "../api/sources";
import type { ClaimListItem } from "../api/types";

type SourceClaimsPanelProps = {
  kbId: string;
  sourceId: string;
};

export function SourceClaimsPanel({ kbId, sourceId }: SourceClaimsPanelProps) {
  const [claims, setClaims] = useState<ClaimListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    fetchSourceClaims(kbId, sourceId)
      .then((items) => {
        if (active) {
          setClaims(items);
        }
      })
      .catch(() => {
        if (active) {
          setError("萃取结果加载失败。");
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
    return <p className="form-helper">正在加载萃取结果…</p>;
  }

  if (error) {
    return <p className="form-helper">{error}</p>;
  }

  if (claims.length === 0) {
    return <p className="form-helper">该文档尚未萃取到 Claim。</p>;
  }

  return (
    <div className="claims-panel">
      <table>
        <thead>
          <tr>
            <th>主体</th>
            <th>谓词</th>
            <th>客体</th>
            <th>状态</th>
            <th>置信度</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.id}>
              <td>{claim.subject}</td>
              <td>{claim.predicate}</td>
              <td>{claim.object}</td>
              <td>{claim.status}</td>
              <td>{Math.round(claim.confidence * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
