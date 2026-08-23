import { useEffect, useRef, useState } from "react";

import { getThemePreference, setThemePreference, type ThemePreference } from "../theme";
import { Button } from "./Button";

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "system", label: "System" },
  { value: "dark", label: "Dark" },
];

const LABELS: Record<ThemePreference, string> = {
  light: "Light",
  system: "System",
  dark: "Dark",
};

/** Nav's account-cluster theme picker (DESIGN_SYSTEM_REFRESH.md §11) —
 * text-only, no icons, matching the rest of this app's icon-free
 * convention. Esc/click-outside close behavior mirrors SlideOverPanel's,
 * just via a ref instead of a full-screen overlay (this is a small
 * anchored popover, not a page-level panel). */
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(() => getThemePreference());
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  function choose(value: ThemePreference) {
    setThemePreference(value);
    setPreference(value);
    setOpen(false);
  }

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <Button variant="text" onClick={() => setOpen((v) => !v)} aria-haspopup="true" aria-expanded={open}>
        {LABELS[preference]}
      </Button>
      {open && (
        <div
          role="menu"
          aria-label="Theme"
          style={{
            position: "absolute",
            top: "100%",
            right: 0,
            marginTop: "var(--space-1)",
            background: "var(--elevation-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-md)",
            padding: "var(--space-1)",
            minWidth: 120,
            zIndex: 10,
          }}
        >
          {OPTIONS.map((option) => {
            const selected = option.value === preference;
            return (
              <button
                key={option.value}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                onClick={() => choose(option.value)}
                className="theme-menu-item"
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  border: "none",
                  background: "transparent",
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "var(--radius-sm)",
                  color: selected ? "var(--text-h)" : "var(--text)",
                  fontWeight: selected ? "var(--weight-semibold)" : "var(--weight-normal)",
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
