import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type EscalationSource = "sla_breach" | "workflow_failure" | "rule_triggered" | "manual";
export type EscalationStatus = "open" | "acknowledged" | "resolved" | "reassigned" | "snoozed";

export interface Escalation {
  id: string;
  source: EscalationSource;
  deal_id: string | null;
  task_id: string | null;
  sla_state_id: string | null;
  workflow_run_id: string | null;
  raised_by: string | null;
  assigned_to: string;
  status: EscalationStatus;
  reason: string | null;
  resolution_note: string | null;
  opened_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  snoozed_until: string | null;
  was_reopened: boolean;
  contact_id: string | null;
  contact_name: string | null;
  rule_name: string | null;
  assigned_to_name: string | null;
}

export async function listEscalations(
  token: string,
  params?: { status?: EscalationStatus },
): Promise<DataEnvelope<Escalation[]>> {
  const query = params?.status ? `?status=${params.status}` : "";
  return apiGet<DataEnvelope<Escalation[]>>(token, `/api/v1/escalations${query}`);
}

export async function raiseEscalation(
  token: string,
  input: { deal_id?: string; task_id?: string; reason: string },
): Promise<DataEnvelope<Escalation>> {
  return apiPost<DataEnvelope<Escalation>>(token, "/api/v1/escalations", input);
}

export async function updateEscalation(
  token: string,
  escalationId: string,
  input: {
    status?: "acknowledged" | "resolved" | "snoozed";
    resolution_note?: string;
    reassign_to?: string;
    snoozed_until?: string;
  },
): Promise<DataEnvelope<Escalation>> {
  return apiPatch<DataEnvelope<Escalation>>(token, `/api/v1/escalations/${escalationId}`, input);
}
