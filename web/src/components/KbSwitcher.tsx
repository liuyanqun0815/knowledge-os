import { useEffect, useState } from "react";
import { listKnowledgeBases } from "../api/knowledgeBases";
import type { KnowledgeBase } from "../api/types";
import { useKb } from "../app/KbContext";
import { ErrorBanner } from "./ErrorBanner";

export function KbSwitcher() {
  const { kbId, setKbId, clearKb } = useKb();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;

    listKnowledgeBases()
      .then((items) => {
        if (active) {
          setKnowledgeBases(items);
        }
      })
      .catch(() => {
        if (active) {
          setError("知识库列表加载失败，请检查 API 或管理员令牌。");
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
  }, []);

  return (
    <div className="kb-switcher">
      <label htmlFor="kb-switcher">当前库</label>
      <select
        id="kb-switcher"
        value={kbId ?? ""}
        onChange={(event) => {
          const id = event.target.value;
          if (id) {
            setKbId(id);
          } else {
            clearKb();
          }
        }}
        disabled={isLoading}
      >
        <option value="">{isLoading ? "加载中…" : "请选择知识库"}</option>
        {knowledgeBases.map((knowledgeBase) => (
          <option key={knowledgeBase.id} value={knowledgeBase.id}>
            {knowledgeBase.name}
          </option>
        ))}
      </select>
      {error ? <ErrorBanner message={error} /> : null}
    </div>
  );
}
