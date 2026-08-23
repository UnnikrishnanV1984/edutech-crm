import type { PipelineStage } from "./api/pipelineStages";

export interface ColorTone {
  bg: string;
  fg: string;
  border: string;
}

// Position-based, not name-based — pipeline_stages are tenant-configurable
// (name and count), so a fixed name->color map would break the moment a
// tenant renames a stage or two tenants pick colliding names
// (DESIGN_SYSTEM_REFRESH.md §8). Deliberately excludes the accent's violet
// hue, so a stage color never competes with a primary-action button.
// fg values tuned to clear WCAG AA 4.5:1 against their own bg (verified
// numerically — see DESIGN_SYSTEM_REFRESH.md's contrast-check note).
const STAGE_COLOR_SEQUENCE: { light: ColorTone; dark: ColorTone }[] = [
  { light: { bg: "#e6f1fc", fg: "#1f6fb8", border: "#c9e2f7" }, dark: { bg: "#16283a", fg: "#7ec1f2", border: "#234a68" } }, // sky
  { light: { bg: "#e1f5f1", fg: "#0f6c60", border: "#bfe8df" }, dark: { bg: "#123430", fg: "#5fd8c4", border: "#1d5348" } }, // teal
  { light: { bg: "#fdf1de", fg: "#a15c07", border: "#f6ddad" }, dark: { bg: "#3a2a10", fg: "#f0b84e", border: "#5c431c" } }, // amber
  { light: { bg: "#fce8ee", fg: "#b23760", border: "#f6cddb" }, dark: { bg: "#3a1c28", fg: "#f4a0bb", border: "#5c2d3f" } }, // rose
  { light: { bg: "#eef3e3", fg: "#4d6c26", border: "#d9e6c2" }, dark: { bg: "#26301a", fg: "#b7d688", border: "#3c4d28" } }, // sage
  { light: { bg: "#eceef2", fg: "#4b5567", border: "#d7dce4" }, dark: { bg: "#22242e", fg: "#b7bccb", border: "#343747" } }, // slate
];

const WON_TONE = { light: { bg: "#e6f7ef", fg: "#0e6e4a", border: "#c7ecdc" }, dark: { bg: "#163829", fg: "#6ee7b0", border: "#245a3f" } };
// LOST_TONE.light.fg is its own darker value, not a straight reuse of
// --text-muted — --text-muted is tuned against --bg, not against this
// tone's own pastel background, and reusing it fell short of 4.5:1 here.
const LOST_TONE = { light: { bg: "#f1eff5", fg: "#68617a", border: "#e6e3ec" }, dark: { bg: "#21222c", fg: "#8d8fa3", border: "#2b2c38" } };

function prefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

/** The raw 6-hue sequence, exposed for Avatar.tsx's deterministic
 * hash-by-user-id color assignment (DESIGN_SYSTEM_REFRESH.md §10) — reuses
 * the same palette rather than introducing a seventh one. */
export function toneByIndex(index: number): ColorTone {
  const entry = STAGE_COLOR_SEQUENCE[index % STAGE_COLOR_SEQUENCE.length] ?? STAGE_COLOR_SEQUENCE[0]!;
  return prefersDark() ? entry.dark : entry.light;
}

export const STAGE_HUE_COUNT = STAGE_COLOR_SEQUENCE.length;

/** Returns the {bg, fg, border} pastel-chip triple for a stage — is_won/
 * is_lost override the position color entirely (DESIGN_SYSTEM_REFRESH.md
 * §8), since those two flags carry fixed meaning regardless of what the
 * tenant named/ordered the stage. */
export function stageColor(stage: PipelineStage, index: number): ColorTone {
  const dark = prefersDark();
  if (stage.is_won) return dark ? WON_TONE.dark : WON_TONE.light;
  if (stage.is_lost) return dark ? LOST_TONE.dark : LOST_TONE.light;
  const entry = STAGE_COLOR_SEQUENCE[index % STAGE_COLOR_SEQUENCE.length] ?? STAGE_COLOR_SEQUENCE[5];
  return dark ? entry!.dark : entry!.light;
}

export function stageIcon(stage: PipelineStage): string | undefined {
  if (stage.is_won) return "✓";
  if (stage.is_lost) return "–";
  return undefined;
}
