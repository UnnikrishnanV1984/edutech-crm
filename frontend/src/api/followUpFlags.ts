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
}

export async function listFollowUpFlags(token: string): Promise<DataEnvelope<FollowUpFlag[]>> {
  return apiGet<DataEnvelope<FollowUpFlag[]>>(token, "/api/v1/follow-up-flags");
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
