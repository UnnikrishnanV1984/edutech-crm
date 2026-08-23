import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";

import { config } from "../config/index.js";

export interface KeycloakClaims extends JWTPayload {
  sub: string;
  tenant_id?: string;
  email?: string;
  name?: string;
  realm_access?: { roles?: string[] };
}

// admin/manager/counselor per DATABASE_SCHEMA.md's users.role CHECK
// constraint — kept in sync manually since the two live in different
// languages/services.
const APP_ROLES = ["admin", "manager", "counselor"] as const;

let jwks: ReturnType<typeof createRemoteJWKSet> | undefined;

// Lazy singleton: created on first use, not at module load, so importing
// this module doesn't require KEYCLOAK_JWKS_URL to be set (keeps unrelated
// unit tests importable without full env config). jose caches fetched keys
// internally and only refetches on an unknown `kid` (rate-limited).
function getJwks(): ReturnType<typeof createRemoteJWKSet> {
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(config.keycloakJwksUrl));
  }
  return jwks;
}

export async function verifyAccessToken(token: string): Promise<KeycloakClaims> {
  const { payload } = await jwtVerify(token, getJwks(), {
    issuer: config.keycloakIssuerUrl,
    audience: config.keycloakClientId,
  });
  return payload as KeycloakClaims;
}

// realm_access.roles also contains Keycloak's own default composite role
// (default-roles-<realm>) and scope-derived entries (offline_access,
// uma_authorization) — this picks out exactly one of our three app roles,
// or undefined if zero or more than one match (ambiguous — reject rather
// than guess).
export function extractAppRole(roles: string[] | undefined): string | undefined {
  const matches = (roles ?? []).filter((role): role is (typeof APP_ROLES)[number] =>
    (APP_ROLES as readonly string[]).includes(role),
  );
  return matches.length === 1 ? matches[0] : undefined;
}
