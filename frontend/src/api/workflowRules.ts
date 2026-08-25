import { apiGet, apiPatch, apiPost } from "./client";
import type { CollectionEnvelope, DataEnvelope } from "./types";

export type TriggerType = "stage_changed" | "lead_created" | "task_overdue" | "elapsed_time";
export type ActionType =
  | "assign_round_robin"
  | "assign_by_territory"
  | "create_task"
  | "change_stage"
  | "notify_manager"
  | "raise_escalation"
  | "send_message";

export interface WorkflowCondition {
  field: string;
  op: "eq" | "in";
  value: unknown;
}

export interface WorkflowAction {
  type: ActionType;
  config?: Record<string, unknown>;
}

export interface WorkflowRule {
  id: string;
  name: string;
  trigger_type: TriggerType;
  trigger_config: Record<string, unknown>;
  conditions: WorkflowCondition[];
  actions: WorkflowAction[];
  status: "draft" | "pending_approval" | "active" | "disabled";
  created_by: string;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRun {
  id: string;
  workflow_rule_id: string;
  rule_name: string;
  trigger_source_type: string;
  trigger_source_id: string;
  status: "success" | "failed" | "retrying" | "skipped_unavailable";
  attempt: number;
  error_message: string | null;
  executed_at: string;
}

export interface WorkflowTestRunMatch {
  type: string;
  id: string;
  label: string;
}

export interface WorkflowTestRunResult {
  candidates_checked: number;
  matched: WorkflowTestRunMatch[];
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
    conditions?: WorkflowCondition[];
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

// Full-field edit — admin only (backend-enforced). Distinct from
// decideWorkflowRule above, which only ever sends status, so approve/
// reject stays a one-field call even though the endpoint accepts more.
export async function updateWorkflowRule(
  token: string,
  ruleId: string,
  input: Partial<{
    name: string;
    trigger_config: Record<string, unknown>;
    conditions: WorkflowCondition[];
    actions: WorkflowAction[];
    status: "draft" | "active" | "disabled";
  }>,
): Promise<DataEnvelope<WorkflowRule>> {
  return apiPatch<DataEnvelope<WorkflowRule>>(token, `/api/v1/workflow-rules/${ruleId}`, input);
}

export async function listWorkflowRuns(
  token: string,
  params: { rule_id?: string; page?: number; page_size?: number } = {},
): Promise<CollectionEnvelope<WorkflowRun>> {
  const search = new URLSearchParams();
  if (params.rule_id) search.set("rule_id", params.rule_id);
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  const query = search.toString();
  return apiGet<CollectionEnvelope<WorkflowRun>>(
    token,
    `/api/v1/workflow-rules/runs${query ? `?${query}` : ""}`,
  );
}

export async function testRunWorkflowRule(
  token: string,
  input: {
    trigger_type: TriggerType;
    trigger_config?: Record<string, unknown>;
    conditions?: WorkflowCondition[];
  },
): Promise<DataEnvelope<WorkflowTestRunResult>> {
  return apiPost<DataEnvelope<WorkflowTestRunResult>>(
    token,
    "/api/v1/workflow-rules/test-run",
    input,
  );
}
