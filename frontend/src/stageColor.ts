import type { PipelineStage } from "./api/pipelineStages";

// Position-based, not name-based — pipeline_stages are tenant-configurable
// (name and count), so a fixed name→color map would break the moment a
// tenant renames a stage or two tenants pick colliding names
// (PHASE_1_UI_DESIGN.md's design tokens section).
const STAGE_COLOR_SEQUENCE = ["#5b8def", "#a855f7", "#d97706", "#0d9488", "#ec4899", "#64748b"];

export function stageColor(stage: PipelineStage, index: number): string {
  if (stage.is_won) {
    return "var(--success)";
  }
  if (stage.is_lost) {
    return "var(--text-muted)";
  }
  return STAGE_COLOR_SEQUENCE[index % STAGE_COLOR_SEQUENCE.length] ?? "#64748b";
}

export function stageIcon(stage: PipelineStage): string | undefined {
  if (stage.is_won) return "✓";
  if (stage.is_lost) return "–";
  return undefined;
}
