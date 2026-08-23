import { config } from "../config";

export interface ApiErrorDetail {
  field?: string;
  issue?: string;
  [key: string]: unknown;
}

interface ErrorEnvelope {
  error: { code: string; message: string; details?: ApiErrorDetail[] };
  meta: { request_id: string };
}

export class ApiRequestError extends Error {
  code: string;
  details?: ApiErrorDetail[];

  constructor(code: string, message: string, details?: ApiErrorDetail[]) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

async function request<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (init?.body) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${config.bffBaseUrl}${path}`, { ...init, headers });
  const body: unknown = await response.json();
  if (!response.ok) {
    const errBody = body as ErrorEnvelope;
    throw new ApiRequestError(errBody.error.code, errBody.error.message, errBody.error.details);
  }
  return body as T;
}

export function apiGet<T>(token: string, path: string): Promise<T> {
  return request<T>(token, path);
}

export function apiPost<T>(token: string, path: string, data: unknown): Promise<T> {
  return request<T>(token, path, { method: "POST", body: JSON.stringify(data) });
}

export function apiPatch<T>(token: string, path: string, data: unknown): Promise<T> {
  return request<T>(token, path, { method: "PATCH", body: JSON.stringify(data) });
}
