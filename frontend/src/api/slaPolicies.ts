import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type SlaAppliesTo = "stage_entry" | "task_due";

export interface SlaPolicy {
  id: string;
  name: string;
  applies_to: SlaAppliesTo;
  stage_id: string | null;
  task_type: string | null;
  target_minutes: number;
  warning_threshold_pct: number;
  status: "active" | "disabled";
  created_at: string;
  updated_at: string;
}

export async function listSlaPolicies(token: string): Promise<DataEnvelope<SlaPolicy[]>> {
  return apiGet<DataEnvelope<SlaPolicy[]>>(token, "/api/v1/sla-policies");
}

export async function createSlaPolicy(
  token: string,
  input: {
    name: string;
    applies_to: SlaAppliesTo;
    stage_id?: string;
    target_minutes: number;
    warning_threshold_pct?: number;
  },
): Promise<DataEnvelope<SlaPolicy>> {
  return apiPost<DataEnvelope<SlaPolicy>>(token, "/api/v1/sla-policies", input);
}

export async function setSlaPolicyStatus(
  token: string,
  policyId: string,
  status: "active" | "disabled",
): Promise<DataEnvelope<SlaPolicy>> {
  return apiPatch<DataEnvelope<SlaPolicy>>(token, `/api/v1/sla-policies/${policyId}`, { status });
}
