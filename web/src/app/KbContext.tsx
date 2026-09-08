import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

const CURRENT_KB_KEY = "akos_current_kb";

type KbContextValue = {
  kbId: string | null;
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

  useEffect(() => {
    if (urlKbId && urlKbId !== kbId) {
      setCurrentKbId(urlKbId);
      localStorage.setItem(CURRENT_KB_KEY, urlKbId);
    }
  }, [kbId, urlKbId]);

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
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("kb");
      return next;
    });
  }, [setSearchParams]);

  const value = useMemo(() => ({ kbId, setKbId, clearKb }), [clearKb, kbId, setKbId]);

  return <KbContext.Provider value={value}>{children}</KbContext.Provider>;
}

export function useKb(): KbContextValue {
  const context = useContext(KbContext);
  if (!context) {
    throw new Error("useKb 必须在 KbProvider 内使用");
  }
  return context;
}
