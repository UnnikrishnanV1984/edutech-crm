// lead_source is a fixed backend enum, not tenant-configurable, so direct
// per-value color is safe here — unlike pipeline stages (see stageColor.ts).
const LEAD_SOURCE_COLORS: Record<string, string> = {
  meta: "#5b8def",
  google: "#d97706",
  web: "#64748b",
  whatsapp: "#22c55e",
  manual: "#9a94a3",
};

const LEAD_SOURCE_LABELS: Record<string, string> = {
  meta: "Meta",
  google: "Google",
  web: "Web",
  whatsapp: "WhatsApp",
  manual: "Manual",
};

export function leadSourceColor(source: string): string {
  return LEAD_SOURCE_COLORS[source] ?? "#9a94a3";
}

export function leadSourceLabel(source: string): string {
  return LEAD_SOURCE_LABELS[source] ?? source;
}
