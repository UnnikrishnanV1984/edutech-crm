import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type TriggerType = "stage_changed" | "lead_created" | "task_overdue" | "elapsed_time";
export type ActionType =
  | "assign_round_robin"
  | "assign_by_territory"
  | "create_task"
  | "change_stage"
  | "notify_manager"
  | "raise_escalation"
  | "send_message";

export interface WorkflowAction {
  type: ActionType;
  config?: Record<string, unknown>;
}

export interface WorkflowRule {
  id: string;
  name: string;
  trigger_type: TriggerType;
  trigger_config: Record<string, unknown>;
  conditions: unknown[];
  actions: WorkflowAction[];
  status: "draft" | "pending_approval" | "active" | "disabled";
  created_by: string;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
}

export async function listWorkflowRules(token: string): Promise<DataEnvelope<WorkflowRule[]>> {
  return apiGet<DataEnvelope<WorkflowRule[]>>(token, "/api/v1/workflow-rules");
}

export async function createWorkflowRule(
  token: string,
  input: {
    name: string;
    trigger_type: TriggerType;
    trigger_config?: Record<string, unknown>;
    actions: WorkflowAction[];
    status?: "draft" | "active";
  },
): Promise<DataEnvelope<WorkflowRule>> {
  return apiPost<DataEnvelope<WorkflowRule>>(token, "/api/v1/workflow-rules", input);
}

export async function decideWorkflowRule(
  token: string,
  ruleId: string,
  status: "active" | "disabled",
): Promise<DataEnvelope<WorkflowRule>> {
  return apiPatch<DataEnvelope<WorkflowRule>>(token, `/api/v1/workflow-rules/${ruleId}`, {
    status,
  });
}
