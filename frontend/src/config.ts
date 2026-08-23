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
};
