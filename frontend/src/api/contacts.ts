import { apiGet, apiPatch, apiPost } from "./client";
import type { CollectionEnvelope, DataEnvelope } from "./types";

export interface Contact {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  lead_source: string;
  owner_id: string;
  status: string;
  territory: string | null;
  created_at: string;
  updated_at: string;
  // The contact's most-recently-updated deal, if any — null when the
  // contact has no deal yet.
  current_deal_id: string | null;
  stage_id: string | null;
  stage_name: string | null;
  sla_state: "on_track" | "at_risk" | "breached" | null;
  sla_target_at: string | null;
  sla_target_minutes: number | null;
  has_open_follow_up: boolean;
}

export interface ContactListParams {
  search?: string;
  lead_source?: string;
  owner_id?: string;
  stage_id?: string;
  has_follow_up_flag?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
  // Batch-fetch a known set of contacts (e.g. resolving each deal/task's
  // contact) in one request instead of one GET per contact — pagination
  // params are ignored by the backend when this is set.
  ids?: string[];
}

export interface ContactCreateInput {
  full_name: string;
  email?: string;
  phone?: string;
  lead_source: string;
  owner_id?: string;
  territory?: string;
}

function buildQuery(
  params: Record<string, string | number | boolean | string[] | undefined>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, item);
    } else {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export async function listContacts(
  token: string,
  params: ContactListParams = {},
): Promise<CollectionEnvelope<Contact>> {
  return apiGet<CollectionEnvelope<Contact>>(
    token,
    `/api/v1/contacts${buildQuery(params as Record<string, string | number | boolean | string[] | undefined>)}`,
  );
}

export async function getContact(token: string, contactId: string): Promise<DataEnvelope<Contact>> {
  return apiGet<DataEnvelope<Contact>>(token, `/api/v1/contacts/${contactId}`);
}

export async function createContact(
  token: string,
  input: ContactCreateInput,
): Promise<DataEnvelope<Contact>> {
  return apiPost<DataEnvelope<Contact>>(token, "/api/v1/contacts", input);
}

export async function updateContact(
  token: string,
  contactId: string,
  input: Partial<ContactCreateInput>,
): Promise<DataEnvelope<Contact>> {
  return apiPatch<DataEnvelope<Contact>>(token, `/api/v1/contacts/${contactId}`, input);
}

export interface Activity {
  id: string;
  contact_id: string;
  deal_id: string | null;
  type: string;
  actor_id: string;
  payload:
    | { old_stage_id: string; new_stage_id: string }
    | { note: string; channel: string }
    | Record<string, unknown>
    | null;
  created_at: string;
}

export async function listContactActivities(
  token: string,
  contactId: string,
): Promise<DataEnvelope<Activity[]>> {
  return apiGet<DataEnvelope<Activity[]>>(token, `/api/v1/contacts/${contactId}/activities`);
}

export type ActivityChannel = "call" | "email" | "whatsapp" | "note";

export async function logActivity(
  token: string,
  contactId: string,
  input: { note: string; channel?: ActivityChannel },
): Promise<DataEnvelope<Activity>> {
  return apiPost<DataEnvelope<Activity>>(token, `/api/v1/contacts/${contactId}/activities`, input);
}
