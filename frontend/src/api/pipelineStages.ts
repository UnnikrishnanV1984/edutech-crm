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
