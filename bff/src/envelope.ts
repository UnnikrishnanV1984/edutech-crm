export interface ErrorDetail {
  field: string;
  issue: string;
}

export function dataEnvelope<T>(
  data: T,
  requestId: string,
  extraMeta?: Record<string, unknown>,
): { data: T; meta: Record<string, unknown> } {
  return { data, meta: { request_id: requestId, ...extraMeta } };
}

export function errorEnvelope(
  code: string,
  message: string,
  requestId: string,
  details?: ErrorDetail[],
): { error: Record<string, unknown>; meta: Record<string, unknown> } {
  const error: Record<string, unknown> = { code, message };
  if (details) {
    error.details = details;
  }
  return { error, meta: { request_id: requestId } };
}
