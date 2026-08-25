import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export interface FollowUpFlag {
  id: string;
  manager_id: string;
  deal_id: string | null;
  contact_id: string | null;
  note: string;
  remind_on: string;
  resolved_at: string | null;
  created_at: string;
  resolved_contact_id: string | null;
  contact_name: string | null;
  manager_name: string | null;
}

export async function listFollowUpFlags(
  token: string,
  params: { contact_id?: string; manager_id?: string } = {},
): Promise<DataEnvelope<FollowUpFlag[]>> {
  const search = new URLSearchParams();
  if (params.contact_id) search.set("contact_id", params.contact_id);
  if (params.manager_id) search.set("manager_id", params.manager_id);
  const query = search.toString();
  return apiGet<DataEnvelope<FollowUpFlag[]>>(
    token,
    `/api/v1/follow-up-flags${query ? `?${query}` : ""}`,
  );
}

export async function createFollowUpFlag(
  token: string,
  input: { deal_id?: string; contact_id?: string; note: string; remind_on: string },
): Promise<DataEnvelope<FollowUpFlag>> {
  return apiPost<DataEnvelope<FollowUpFlag>>(token, "/api/v1/follow-up-flags", input);
}

export async function resolveFollowUpFlag(
  token: string,
  flagId: string,
): Promise<DataEnvelope<FollowUpFlag>> {
  return apiPatch<DataEnvelope<FollowUpFlag>>(token, `/api/v1/follow-up-flags/${flagId}`, {});
}

export async function snoozeFollowUpFlag(
  token: string,
  flagId: string,
  remindOn: string,
): Promise<DataEnvelope<FollowUpFlag>> {
  return apiPatch<DataEnvelope<FollowUpFlag>>(token, `/api/v1/follow-up-flags/${flagId}`, {
    remind_on: remindOn,
  });
}
