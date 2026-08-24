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
}

export interface ContactListParams {
  search?: string;
  lead_source?: string;
  owner_id?: string;
  page?: number;
  page_size?: number;
}

export interface ContactCreateInput {
  full_name: string;
  email?: string;
  phone?: string;
  lead_source: string;
  owner_id?: string;
  territory?: string;
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

export async function listContacts(
  token: string,
  params: ContactListParams = {},
): Promise<CollectionEnvelope<Contact>> {
  return apiGet<CollectionEnvelope<Contact>>(
    token,
    `/api/v1/contacts${buildQuery(params as Record<string, string | number | undefined>)}`,
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
  payload: { old_stage_id: string; new_stage_id: string } | null;
  created_at: string;
}

export async function listContactActivities(
  token: string,
  contactId: string,
): Promise<DataEnvelope<Activity[]>> {
  return apiGet<DataEnvelope<Activity[]>>(token, `/api/v1/contacts/${contactId}/activities`);
}
