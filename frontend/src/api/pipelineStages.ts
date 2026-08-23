import { apiGet, apiPatch } from "./client";
import type { DataEnvelope } from "./types";

export interface PipelineStage {
  id: string;
  name: string;
  sort_order: number;
  is_won: boolean;
  is_lost: boolean;
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
