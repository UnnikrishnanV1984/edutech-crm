import { apiGet } from "./client";
import type { DataEnvelope } from "./types";

// Read-only, by design — PIPELINE_AND_REVENUE.md §2.6. Selecting a
// template never writes here; it prefills POST /api/v1/pipeline-stages
// (see createPipelineStage), which lands on the tenant's own row.
export interface PipelineStageTemplate {
  id: string;
  name: string;
  category: string;
  default_sort_order: number;
  is_won: boolean;
  is_lost: boolean;
  is_invoice_stage: boolean;
  is_rework_stage: boolean;
  default_win_probability_pct: number;
  created_at: string;
}

export async function listPipelineStageTemplates(
  token: string,
): Promise<DataEnvelope<PipelineStageTemplate[]>> {
  return apiGet<DataEnvelope<PipelineStageTemplate[]>>(token, "/api/v1/pipeline-stage-templates");
}
