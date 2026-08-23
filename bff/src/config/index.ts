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
  // Browser origin the SPA is served from — the BFF talks to the browser's
  // auth session (CLAUDE.md rule 4), so it's the one service that needs to
  // answer CORS preflights for it. Defaults to the local Vite dev origin.
  get corsOrigin(): string {
    return optional("CORS_ORIGIN", "http://localhost:5173");
  },
};
