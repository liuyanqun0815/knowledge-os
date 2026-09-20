import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getKnowledgeBase } from "../api/knowledgeBases";

const CURRENT_KB_KEY = "akos_current_kb";

type KbContextValue = {
  kbId: string | null;
  graphEnabled: boolean | null;
  setKbId: (id: string) => void;
  clearKb: () => void;
};

const KbContext = createContext<KbContextValue | null>(null);

export function KbProvider({ children }: { children: React.ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlKbId = searchParams.get("kb");
  const [kbId, setCurrentKbId] = useState<string | null>(() => {
    if (urlKbId) {
      localStorage.setItem(CURRENT_KB_KEY, urlKbId);
      return urlKbId;
    }
    return localStorage.getItem(CURRENT_KB_KEY);
  });
  const [graphEnabled, setGraphEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    if (urlKbId && urlKbId !== kbId) {
      setCurrentKbId(urlKbId);
      localStorage.setItem(CURRENT_KB_KEY, urlKbId);
    }
  }, [kbId, urlKbId]);

  useEffect(() => {
    if (!kbId) {
      setGraphEnabled(null);
      return;
    }
    let active = true;
    getKnowledgeBase(kbId)
      .then((item) => {
        if (active) {
          setGraphEnabled(item.graph_enabled !== false);
        }
      })
      .catch(() => {
        if (active) {
          setGraphEnabled(null);
        }
      });
    return () => {
      active = false;
    };
  }, [kbId]);

  useEffect(() => {
    function refreshGraphFlag() {
      if (!kbId) {
        return;
      }
      getKnowledgeBase(kbId)
        .then((item) => setGraphEnabled(item.graph_enabled !== false))
        .catch(() => undefined);
    }
    window.addEventListener("akos:kb-list-changed", refreshGraphFlag);
    return () => window.removeEventListener("akos:kb-list-changed", refreshGraphFlag);
  }, [kbId]);

  const setKbId = useCallback(
    (id: string) => {
      localStorage.setItem(CURRENT_KB_KEY, id);
      setCurrentKbId(id);
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("kb", id);
        return next;
      });
    },
    [setSearchParams],
  );

  const clearKb = useCallback(() => {
    localStorage.removeItem(CURRENT_KB_KEY);
    setCurrentKbId(null);
    setGraphEnabled(null);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("kb");
      return next;
    });
  }, [setSearchParams]);

  const value = useMemo(
    () => ({ kbId, graphEnabled, setKbId, clearKb }),
    [clearKb, graphEnabled, kbId, setKbId],
  );

  return <KbContext.Provider value={value}>{children}</KbContext.Provider>;
}

export function useKb(): KbContextValue {
  const context = useContext(KbContext);
  if (!context) {
    throw new Error("useKb 必须在 KbProvider 内使用");
  }
  return context;
}
