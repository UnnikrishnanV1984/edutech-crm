import type { ColorTone } from "./stageColor";

// lead_source is a fixed backend enum, not tenant-configurable, so direct
// per-value color is safe here — unlike pipeline stages (see stageColor.ts).
// fg values tuned to clear WCAG AA 4.5:1 against their own bg (verified
// numerically — see DESIGN_SYSTEM_REFRESH.md's contrast-check note).
const LEAD_SOURCE_COLORS: Record<string, { light: ColorTone; dark: ColorTone }> = {
  meta: { light: { bg: "#e8ecfd", fg: "#3f4fc7", border: "#cfd6f7" }, dark: { bg: "#1d2140", fg: "#a3b0f5", border: "#2e3560" } },
  google: { light: { bg: "#fdefdd", fg: "#9c4a09", border: "#f6d9ad" }, dark: { bg: "#3a2410", fg: "#f5a355", border: "#5c3a1c" } },
  web: { light: { bg: "#eceef2", fg: "#4b5567", border: "#d7dce4" }, dark: { bg: "#22242e", fg: "#b7bccb", border: "#343747" } },
  whatsapp: { light: { bg: "#e3f7e6", fg: "#187233", border: "#c3ebca" }, dark: { bg: "#163a1e", fg: "#6fd88a", border: "#235c30" } },
  manual: { light: { bg: "#f1eef5", fg: "#6b5f7a", border: "#ded6e6" }, dark: { bg: "#241f2e", fg: "#b8a8c7", border: "#372f45" } },
};

const LEAD_SOURCE_LABELS: Record<string, string> = {
  meta: "Meta",
  google: "Google",
  web: "Web",
  whatsapp: "WhatsApp",
  manual: "Manual",
};

function prefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

export function leadSourceColor(source: string): ColorTone {
  const entry = LEAD_SOURCE_COLORS[source] ?? LEAD_SOURCE_COLORS.web!;
  return prefersDark() ? entry.dark : entry.light;
}

export function leadSourceLabel(source: string): string {
  return LEAD_SOURCE_LABELS[source] ?? source;
}
