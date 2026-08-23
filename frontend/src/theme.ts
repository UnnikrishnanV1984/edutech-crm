export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "theme-preference";

/** "system" is never itself written to storage — its absence (or any
 * other unrecognized value) *is* "system", so a corrupted/stale value
 * degrades to the safe default instead of erroring. */
export function getThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark") {
      return value;
    }
  } catch {
    // localStorage unavailable (private browsing, etc.) — fall back to system.
  }
  return "system";
}

/** Persists the choice and applies it immediately via the data-theme
 * attribute index.css's cascade (DESIGN_SYSTEM_REFRESH.md §11) keys off
 * of. Mirrors the inline script in index.html that applies the stored
 * choice before first paint — same storage key, same attribute. */
export function setThemePreference(preference: ThemePreference): void {
  try {
    if (preference === "system") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, preference);
    }
  } catch {
    // Best-effort persistence only — theme still applies for this session.
  }
  applyThemeAttribute(preference);
}

function applyThemeAttribute(preference: ThemePreference): void {
  if (preference === "system") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = preference;
  }
}
