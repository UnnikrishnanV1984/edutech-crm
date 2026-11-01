import { useEffect, useRef, useState } from "react";

import {
  getThemePalette,
  getThemePreference,
  setThemePalette,
  setThemePreference,
  type ThemePalette,
  type ThemePreference,
} from "../theme";

// Plain Unicode glyphs, not an icon library — this app has no icon dependency.
const OPTIONS: { value: ThemePreference; glyph: string; label: string }[] = [
  { value: "light", glyph: "☀", label: "Light" },
  { value: "system", glyph: "◐", label: "System" },
  { value: "dark", glyph: "☾", label: "Dark" },
];

const PALETTES: { value: ThemePalette; label: string; blurb: string; swatch: string[] }[] = [
  { value: "meridian", label: "Meridian", blurb: "Navy and electric blue", swatch: ["#0b1b3a", "#2b59ff", "#12a58a", "#ff6b4a"] },
  { value: "ember", label: "Ember", blurb: "Warm charcoal and orange", swatch: ["#201812", "#ff7a3d", "#12a57a", "#7a5af0"] },
];

/** Sidebar-footer theme control. Light and Dark open an upward popover to
 * pick the palette (Meridian or Ember); System closes it and is always
 * Meridian, following the OS light/dark setting. The popover opens upward
 * because the control sits at the bottom of the sidebar. */
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(() => getThemePreference());
  const [palette, setPalette] = useState<ThemePalette>(() => getThemePalette());
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function chooseMode(value: ThemePreference) {
    setThemePreference(value);
    setPreference(value);
    if (value === "system") setPalette("meridian");
    // Light/Dark offer a palette choice; clicking the active one toggles the popup.
    setOpen(value === "system" ? false : value !== preference || !open);
  }

  function choosePalette(value: ThemePalette) {
    setThemePalette(value);
    setPalette(value);
    setOpen(false);
  }

  const shownPalette = preference === "system" ? "meridian" : palette;

  return (
    <div ref={rootRef} style={{ position: "relative", display: "inline-flex" }}>
      <div
        role="radiogroup"
        aria-label="Theme"
        style={{
          display: "inline-flex",
          gap: 2,
          padding: 2,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
        }}
      >
        {OPTIONS.map((option) => {
          const selected = option.value === preference;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={option.label}
              aria-haspopup={option.value === "system" ? undefined : "dialog"}
              aria-expanded={option.value === "system" ? undefined : selected && open}
              title={option.label}
              onClick={() => chooseMode(option.value)}
              className="theme-segment"
              style={{
                width: 28,
                height: 28,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "none",
                borderRadius: "calc(var(--radius) - 2px)",
                background: selected ? "var(--elevation-2)" : "transparent",
                boxShadow: selected ? "var(--shadow-sm)" : "none",
                color: selected ? "var(--accent)" : "var(--text-muted)",
                fontSize: 14,
                lineHeight: 1,
                padding: 0,
                cursor: "pointer",
              }}
            >
              <span aria-hidden="true">{option.glyph}</span>
            </button>
          );
        })}
      </div>

      {open && preference !== "system" && (
        <div
          role="dialog"
          aria-label="Choose theme"
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: "50%",
            transform: "translateX(-50%)",
            width: 196,
            padding: "var(--space-2)",
            background: "var(--elevation-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 50,
          }}
        >
          <div
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: 700,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: 0.6,
              padding: "2px 6px 6px",
            }}
          >
            {preference === "light" ? "Light" : "Dark"} theme
          </div>
          <div role="radiogroup" aria-label="Theme palette" style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {PALETTES.map((option) => {
              const selected = option.value === shownPalette;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => choosePalette(option.value)}
                  className="theme-segment"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    gap: 4,
                    textAlign: "left",
                    padding: "var(--space-2)",
                    border: selected ? "1px solid var(--accent)" : "1px solid transparent",
                    borderRadius: "var(--radius)",
                    background: selected ? "var(--accent-subtle)" : "transparent",
                    color: "var(--text-h)",
                    cursor: "pointer",
                    font: "inherit",
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700 }}>
                    <span aria-hidden="true" style={{ display: "inline-flex", gap: 2 }}>
                      {option.swatch.map((color) => (
                        <span key={color} style={{ width: 10, height: 10, borderRadius: 3, background: color, border: "1px solid var(--border)" }} />
                      ))}
                    </span>
                    {option.label}
                    {selected && <span aria-hidden="true" style={{ marginLeft: "auto", color: "var(--accent)" }}>✓</span>}
                  </span>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{option.blurb}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
