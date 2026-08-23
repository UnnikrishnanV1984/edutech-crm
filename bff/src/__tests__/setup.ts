// Default env for any test file that builds an app via createApp() but
// doesn't care about the actual proxy/auth target — mirrors backend's
// tests/conftest.py. auth.test.ts overrides these with its own local JWKS
// + stub-backend URLs in its own beforeAll, since it needs specific values.
process.env.BACKEND_BASE_URL ??= "http://127.0.0.1:1";
process.env.KEYCLOAK_ISSUER_URL ??= "http://test-issuer/realms/test";
process.env.KEYCLOAK_JWKS_URL ??= "http://127.0.0.1:1/certs";
process.env.KEYCLOAK_CLIENT_ID ??= "web";
