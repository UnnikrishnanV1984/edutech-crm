import { useSyncExternalStore } from "react";

export type ThemePreference = "light" | "dark" | "system";
export type ThemePalette = "meridian" | "ember";

const MODE_KEY = "theme-preference";
const PALETTE_KEY = "theme-palette";
export const THEME_CHANGE_EVENT = "themechange";

/** "system" is never itself written to storage — its absence (or any
 * other unrecognized value) *is* "system", so a corrupted/stale value
 * degrades to the safe default instead of erroring. */
export function getThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(MODE_KEY);
    if (value === "light" || value === "dark") {
      return value;
    }
  } catch {
    // localStorage unavailable (private browsing, etc.) — fall back to system.
  }
  return "system";
}

/** The palette the user picked in the Light/Dark popup. Meridian is the
 * default; anything unrecognized degrades to it. */
export function getThemePalette(): ThemePalette {
  try {
    if (localStorage.getItem(PALETTE_KEY) === "ember") {
      return "ember";
    }
  } catch {
    // fall through to the default
  }
  return "meridian";
}

/** The palette actually in effect: "System" always means Meridian,
 * regardless of any stored palette choice. */
export function getEffectivePalette(): ThemePalette {
  return getThemePreference() === "system" ? "meridian" : getThemePalette();
}

/** Persists the mode and applies it via the data-theme attribute that
 * index.css's cascade (DESIGN_SYSTEM_REFRESH.md §11-13) keys off of.
 * Choosing System also forces the Meridian palette. Mirrors the inline
 * script in index.html that applies the stored choice before first paint
 * — same storage keys, same attributes. */
export function setThemePreference(preference: ThemePreference): void {
  try {
    if (preference === "system") {
      localStorage.removeItem(MODE_KEY);
    } else {
      localStorage.setItem(MODE_KEY, preference);
    }
  } catch {
    // Best-effort persistence only — theme still applies for this session.
  }
  applyThemeAttributes();
}

/** Persists the palette. Only takes visual effect while the mode is an
 * explicit Light or Dark; System stays Meridian. */
export function setThemePalette(palette: ThemePalette): void {
  try {
    if (palette === "meridian") {
      localStorage.removeItem(PALETTE_KEY);
    } else {
      localStorage.setItem(PALETTE_KEY, palette);
    }
  } catch {
    // Best-effort persistence only.
  }
  applyThemeAttributes();
}

function applyThemeAttributes(): void {
  const root = document.documentElement;
  const mode = getThemePreference();
  if (mode === "system") {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = mode;
  }
  if (getEffectivePalette() === "ember") {
    root.dataset.palette = "ember";
  } else {
    delete root.dataset.palette;
  }
  window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
}

/** Whether the dark variant is currently rendered: an explicit
 * data-theme wins; otherwise the OS preference decides. */
export function isDarkTheme(): boolean {
  if (typeof document !== "undefined") {
    const explicit = document.documentElement.dataset.theme;
    if (explicit === "dark") return true;
    if (explicit === "light") return false;
  }
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

function subscribe(callback: () => void): () => void {
  window.addEventListener(THEME_CHANGE_EVENT, callback);
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  media?.addEventListener?.("change", callback);
  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, callback);
    media?.removeEventListener?.("change", callback);
  };
}

/** Re-renders the caller when the theme changes, so JS-computed colors
 * (stageColor.ts, leadSource.ts) track it. Returns a snapshot string. */
export function useThemeVersion(): string {
  return useSyncExternalStore(
    subscribe,
    () => `${isDarkTheme() ? "dark" : "light"}-${getEffectivePalette()}`,
    () => "light-meridian",
  );
}
