import { apiGet } from "./client";
import type { DataEnvelope } from "./types";

export interface MeUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  status: string;
}

export interface MeTenant {
  id: string;
  slug: string;
  name: string;
}

export type MeResponse = DataEnvelope<{ user: MeUser; tenant: MeTenant }>;

export async function fetchMe(token: string): Promise<MeResponse> {
  return apiGet<MeResponse>(token, "/api/v1/me");
}
