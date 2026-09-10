import { useEffect, useId } from "react";

type SourceContentModalProps = {
  title: string;
  content: string | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
};

export function SourceContentModal({ title, content, isLoading, error, onClose }: SourceContentModalProps) {
  const titleId = useId();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id={titleId}>{title}</h2>
          <button className="button button-secondary" type="button" onClick={onClose} aria-label="关闭预览">
            关闭
          </button>
        </div>
        {isLoading ? <p role="status">正在加载原文…</p> : null}
        {error ? (
          <p className="modal-error" role="alert">
            {error}
          </p>
        ) : null}
        {!isLoading && !error && content !== null ? <pre className="source-content-pre">{content}</pre> : null}
      </div>
    </div>
  );
}
