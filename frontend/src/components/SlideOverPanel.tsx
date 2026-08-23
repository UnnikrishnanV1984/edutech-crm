import type { ReactNode } from "react";
import { useEffect } from "react";

interface SlideOverPanelProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** Shared by create-contact and create-task (PHASE_1_UI_DESIGN.md) — the
 * list/page stays visible behind it, closes on Esc or click-outside. */
export function SlideOverPanel({ title, onClose, children }: SlideOverPanelProps) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.3)",
        display: "flex",
        justifyContent: "flex-end",
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 420,
          maxWidth: "100%",
          height: "100%",
          background: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          padding: 24,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0, fontSize: 18 }}>{title}</h1>
          <button type="button" onClick={onClose} aria-label="Close" style={{ border: "none" }}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
