// The full set of headers the BFF derives from a validated Keycloak token
// and forwards to FastAPI (API_CONVENTIONS.md §1). A client must never be
// able to set any of these directly — see stripForwardedHeaders.ts, which
// runs before auth on every request, and auth.ts, which is the only code
// permitted to set them afterward.
export const FORWARDED_AUTH_HEADERS = [
  "x-tenant-id",
  "x-user-id",
  "x-user-email",
  "x-user-name",
  "x-user-role",
] as const;
