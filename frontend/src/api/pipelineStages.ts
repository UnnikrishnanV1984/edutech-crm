import { apiDelete, apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export interface PipelineStage {
  id: string;
  name: string;
  sort_order: number;
  is_won: boolean;
  is_lost: boolean;
  is_invoice_stage: boolean;
  is_rework_stage: boolean;
  created_at: string;
  updated_at: string;
}

export async function listPipelineStages(token: string): Promise<DataEnvelope<PipelineStage[]>> {
  return apiGet<DataEnvelope<PipelineStage[]>>(token, "/api/v1/pipeline-stages");
}

export async function updatePipelineStage(
  token: string,
  stageId: string,
  input: { name?: string; sort_order?: number },
): Promise<DataEnvelope<PipelineStage>> {
  return apiPatch<DataEnvelope<PipelineStage>>(token, `/api/v1/pipeline-stages/${stageId}`, input);
}

export async function createPipelineStage(
  token: string,
  input: {
    name: string;
    is_won?: boolean;
    is_lost?: boolean;
    is_invoice_stage?: boolean;
    is_rework_stage?: boolean;
  },
): Promise<DataEnvelope<PipelineStage>> {
  return apiPost<DataEnvelope<PipelineStage>>(token, "/api/v1/pipeline-stages", input);
}

export async function deletePipelineStage(
  token: string,
  stageId: string,
): Promise<DataEnvelope<Record<string, never>>> {
  return apiDelete<DataEnvelope<Record<string, never>>>(
    token,
    `/api/v1/pipeline-stages/${stageId}`,
  );
}

export async function reorderPipelineStages(
  token: string,
  stageIds: string[],
): Promise<DataEnvelope<PipelineStage[]>> {
  return apiPatch<DataEnvelope<PipelineStage[]>>(token, "/api/v1/pipeline-stages/reorder", {
    stage_ids: stageIds,
  });
}

// PIPELINE_CONFIG_RESET_PLAN.md §5.1 — full-replacement, not a diff.
// Array order becomes the new sort_order. An entry with no `id` is a new
// stage; is_won/is_lost/is_invoice_stage/is_rework_stage are only read
// for those (creation-only, same rule as createPipelineStage) — present-
// and-ignored on an existing entry, matching the backend's own schema.
export interface PipelineStageBatchEntry {
  id?: string;
  name: string;
  is_won?: boolean;
  is_lost?: boolean;
  is_invoice_stage?: boolean;
  is_rework_stage?: boolean;
}

export async function batchUpdatePipelineStages(
  token: string,
  stages: PipelineStageBatchEntry[],
): Promise<DataEnvelope<PipelineStage[]>> {
  return apiPost<DataEnvelope<PipelineStage[]>>(token, "/api/v1/pipeline-stages/batch", {
    stages,
  });
}

// The confirm phrase is fixed (backend validates it server-side too, per
// PIPELINE_CONFIG_RESET_PLAN.md §5.2) — the frontend's own gate is the
// type-to-confirm modal, not a parameter here.
export async function resetPipelineStagesToDefault(
  token: string,
): Promise<DataEnvelope<PipelineStage[]>> {
  return apiPost<DataEnvelope<PipelineStage[]>>(token, "/api/v1/pipeline-stages/reset-to-default", {
    confirm: "RESET TO DEFAULT",
  });
}
