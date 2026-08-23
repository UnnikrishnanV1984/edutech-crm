import { config } from "../config";

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

export interface MeResponse {
  data: { user: MeUser; tenant: MeTenant };
  meta: { request_id: string };
}

interface ErrorResponse {
  error: { code: string; message: string };
  meta: { request_id: string };
}

export async function fetchMe(token: string): Promise<MeResponse> {
  const response = await fetch(`${config.bffBaseUrl}/api/v1/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    const message =
      body && typeof body === "object" && "error" in body
        ? (body as ErrorResponse).error.message
        : "Request failed";
    throw new Error(message);
  }
  return body as MeResponse;
}
