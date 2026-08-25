import { apiGet } from "./client";
import type { DataEnvelope } from "./types";

export interface TenantUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  manager_id: string | null;
  status: string;
  territory: string | null;
}

export async function listUsers(token: string): Promise<DataEnvelope<TenantUser[]>> {
  return apiGet<DataEnvelope<TenantUser[]>>(token, "/api/v1/users");
}
