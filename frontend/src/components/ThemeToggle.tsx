import { useState } from "react";

import { getThemePreference, setThemePreference, type ThemePreference } from "../theme";

// Plain Unicode glyphs (Miscellaneous Symbols block), not an emoji or an
// SVG icon library — this app has neither dependency, and these render
// as flat monochrome dingbats in system UI fonts rather than colorful
// emoji, which fits an internal admissions tool better than a bright
// icon set would.
const OPTIONS: { value: ThemePreference; glyph: string; label: string }[] = [
  { value: "light", glyph: "☀", label: "Light" }, // ☀
  { value: "system", glyph: "◐", label: "System" }, // ◐
  { value: "dark", glyph: "☾", label: "Dark" }, // ☾
];

/** Sidebar-footer segmented control (superseding DESIGN_SYSTEM_REFRESH.md
 * §11's original "no icons, dropdown" spec — that was written for a Nav
 * dropdown that no longer exists; a popover opening downward from the
 * sidebar footer renders off-screen below the viewport, and three
 * always-visible icons avoid the overflow risk entirely rather than
 * repositioning a popover that shouldn't exist here). The selected
 * option stays visually raised/tinted, not just on :hover — hover is a
 * separate, lighter state on the other two. */
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(() => getThemePreference());

  function choose(value: ThemePreference) {
    setThemePreference(value);
    setPreference(value);
  }

  return (
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
            title={option.label}
            onClick={() => choose(option.value)}
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
  );
}
