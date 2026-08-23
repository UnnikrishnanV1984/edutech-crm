import { apiGet } from "./client";
import type { DataEnvelope } from "./types";

export interface TenantUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  status: string;
}

export async function listUsers(token: string): Promise<DataEnvelope<TenantUser[]>> {
  return apiGet<DataEnvelope<TenantUser[]>>(token, "/api/v1/users");
}
