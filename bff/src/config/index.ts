function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function optional(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

export const config = {
  env: optional("ENVIRONMENT", "development"),
  logLevel: optional("LOG_LEVEL", "info"),
  port: Number(optional("BFF_PORT", "4000")),
  get backendBaseUrl(): string {
    return required("BACKEND_BASE_URL");
  },
  // External/browser-facing issuer URL — must match the `iss` claim exactly,
  // since Keycloak stamps `iss` from the host the browser used to log in.
  get keycloakIssuerUrl(): string {
    return required("KEYCLOAK_ISSUER_URL");
  },
  // Internal (container-to-container) JWKS URL — fine to differ in host
  // from keycloakIssuerUrl; only used to fetch signing keys.
  get keycloakJwksUrl(): string {
    return required("KEYCLOAK_JWKS_URL");
  },
  get keycloakClientId(): string {
    return required("KEYCLOAK_CLIENT_ID");
  },
  // Browser origin(s) the SPA is served from — the BFF talks to the
  // browser's auth session (CLAUDE.md rule 4), so it's the one service
  // that needs to answer CORS preflights for it. Comma-separated so a
  // tunnel (ngrok, etc.) can be allowed alongside the local Vite origin
  // without dropping local dev — defaults to just the local origin.
  get corsOrigins(): string[] {
    return optional("CORS_ORIGIN", "http://localhost:5173")
      .split(",")
      .map((origin) => origin.trim())
      .filter(Boolean);
  },
  // Shared with backend/worker (same REDIS_URL, same Redis instance) —
  // optional with a fallback rather than required(), since rate limiting
  // is defense-in-depth (API_CONVENTIONS.md §8): a misconfigured/
  // unreachable Redis should degrade to "no rate limiting", not take the
  // whole BFF down.
  get redisUrl(): string {
    return optional("REDIS_URL", "redis://redis:6379/0");
  },
  get tenantRateLimitPerMinute(): number {
    return Number(optional("TENANT_RATE_LIMIT_PER_MINUTE", "300"));
  },
};
