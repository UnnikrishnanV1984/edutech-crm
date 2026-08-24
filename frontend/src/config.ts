function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const config = {
  keycloakUrl: required("VITE_KEYCLOAK_URL"),
  keycloakRealm: required("VITE_KEYCLOAK_REALM"),
  keycloakClientId: required("VITE_KEYCLOAK_CLIENT_ID"),
  bffBaseUrl: required("VITE_BFF_BASE_URL"),
  // The FastAPI backend's own public URL — only needed for the
  // embeddable web-form snippet (GAP_FIXES_PLAN.md item 2), which posts
  // directly to POST /webhooks/web on the backend, not through the BFF
  // (that route is deliberately unauthenticated and bypasses the BFF
  // entirely — see backend/app/webhooks/web.py and ARCHITECTURE.md §6's
  // note on /webhooks/*'s separate public ingress path).
  backendPublicUrl: required("VITE_BACKEND_PUBLIC_URL"),
};
