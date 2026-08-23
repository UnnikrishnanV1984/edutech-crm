import { apiGet, apiPatch, apiPost } from "./client";
import type { CollectionEnvelope, DataEnvelope } from "./types";

export interface Task {
  id: string;
  contact_id: string;
  deal_id: string | null;
  assignee_id: string;
  title: string;
  description: string | null;
  due_at: string | null;
  status: "open" | "done";
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListParams {
  assignee_id?: string;
  status?: string;
  contact_id?: string;
  page?: number;
  page_size?: number;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export async function listTasks(
  token: string,
  params: TaskListParams = {},
): Promise<CollectionEnvelope<Task>> {
  return apiGet<CollectionEnvelope<Task>>(
    token,
    `/api/v1/tasks${buildQuery(params as Record<string, string | number | undefined>)}`,
  );
}

export async function createTask(
  token: string,
  input: {
    contact_id: string;
    deal_id?: string;
    assignee_id?: string;
    title: string;
    description?: string;
    due_at?: string;
  },
): Promise<DataEnvelope<Task>> {
  return apiPost<DataEnvelope<Task>>(token, "/api/v1/tasks", input);
}

export async function updateTask(
  token: string,
  taskId: string,
  input: Partial<{
    title: string;
    description: string;
    due_at: string;
    assignee_id: string;
    status: "open" | "done";
  }>,
): Promise<DataEnvelope<Task>> {
  return apiPatch<DataEnvelope<Task>>(token, `/api/v1/tasks/${taskId}`, input);
}
