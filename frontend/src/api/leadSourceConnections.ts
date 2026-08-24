import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type LeadSource = "meta" | "google" | "whatsapp" | "web";
export type ConnectionStatus = "active" | "disabled";

export interface LeadSourceConnection {
  id: string;
  source: LeadSource;
  external_account_id: string;
  status: ConnectionStatus;
  token_expires_at: string | null;
  last_synced_at: string | null;
  conversion_target_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateConnectionInput {
  source: LeadSource;
  external_account_id?: string;
  access_token?: string;
  refresh_token?: string;
}

export async function listConnections(
  token: string,
): Promise<DataEnvelope<LeadSourceConnection[]>> {
  return apiGet<DataEnvelope<LeadSourceConnection[]>>(token, "/api/v1/lead-source-connections");
}

export async function createConnection(
  token: string,
  input: CreateConnectionInput,
): Promise<DataEnvelope<LeadSourceConnection>> {
  return apiPost<DataEnvelope<LeadSourceConnection>>(
    token,
    "/api/v1/lead-source-connections",
    input,
  );
}

export async function setConnectionStatus(
  token: string,
  connectionId: string,
  status: ConnectionStatus,
): Promise<DataEnvelope<LeadSourceConnection>> {
  return apiPatch<DataEnvelope<LeadSourceConnection>>(
    token,
    `/api/v1/lead-source-connections/${connectionId}`,
    { status },
  );
}

export async function setConversionTargetId(
  token: string,
  connectionId: string,
  conversionTargetId: string,
): Promise<DataEnvelope<LeadSourceConnection>> {
  return apiPatch<DataEnvelope<LeadSourceConnection>>(
    token,
    `/api/v1/lead-source-connections/${connectionId}`,
    { conversion_target_id: conversionTargetId },
  );
}

export async function syncConnection(
  token: string,
  connectionId: string,
): Promise<DataEnvelope<{ ingested: number }>> {
  return apiPost<DataEnvelope<{ ingested: number }>>(
    token,
    `/api/v1/lead-source-connections/${connectionId}/sync`,
    {},
  );
}
