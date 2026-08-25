import { apiGet, apiPatch, apiPost } from "./client";
import type { CollectionEnvelope, DataEnvelope } from "./types";

export interface Deal {
  id: string;
  contact_id: string;
  course_id: string | null;
  stage_id: string;
  owner_id: string;
  account_id: string | null;
  value: string;
  currency: string;
  stage_changed_at: string;
  created_at: string;
  updated_at: string;
  sla_state: "on_track" | "at_risk" | "breached" | null;
}

export interface DealListParams {
  stage_id?: string;
  owner_id?: string;
  contact_id?: string;
  course_id?: string;
  sla_state?: string;
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

export async function listDeals(
  token: string,
  params: DealListParams = {},
): Promise<CollectionEnvelope<Deal>> {
  return apiGet<CollectionEnvelope<Deal>>(
    token,
    `/api/v1/deals${buildQuery(params as Record<string, string | number | undefined>)}`,
  );
}

export interface DealWriteInput {
  course_id?: string;
  stage_id?: string;
  owner_id?: string;
  account_id?: string;
  value?: string;
  currency?: string;
}

export async function createDeal(
  token: string,
  contactId: string,
  input: DealWriteInput,
): Promise<DataEnvelope<Deal>> {
  return apiPost<DataEnvelope<Deal>>(token, `/api/v1/contacts/${contactId}/deals`, input);
}

export async function updateDeal(
  token: string,
  dealId: string,
  input: DealWriteInput,
): Promise<DataEnvelope<Deal>> {
  return apiPatch<DataEnvelope<Deal>>(token, `/api/v1/deals/${dealId}`, input);
}
