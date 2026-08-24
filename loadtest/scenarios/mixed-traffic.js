import http from "k6/http";
import { check, sleep } from "k6";

// FEATURES_AND_PLAN.md Phase 5 exit criterion: "load test with simulated
// multi-tenant traffic (skewed tenant sizes)". Runs two scenarios
// concurrently against the same stack — a "large tenant" at 4x the VU
// count of a "small tenant" — so the run genuinely mixes two very
// different per-tenant load levels rather than testing one tenant size
// at a time. Targets the real BFF -> FastAPI -> Postgres chain, not a
// mock, using real Keycloak-issued tokens for the two dev-seeded
// tenants (backend/app/db/seed.py) — same realm, same users, same
// default password tests/test_tenant_isolation.py already relies on.

const KEYCLOAK_ISSUER_URL =
  __ENV.KEYCLOAK_ISSUER_URL || "http://localhost:8080/realms/edutech-crm";
const KEYCLOAK_CLIENT_ID = __ENV.KEYCLOAK_CLIENT_ID || "web";
const BFF_BASE_URL = __ENV.BFF_BASE_URL || "http://localhost:4000";

function fetchToken(username, password) {
  const res = http.post(`${KEYCLOAK_ISSUER_URL}/protocol/openid-connect/token`, {
    grant_type: "password",
    client_id: KEYCLOAK_CLIENT_ID,
    username: username,
    password: password,
  });
  if (res.status !== 200) {
    throw new Error(`token fetch failed for ${username}: ${res.status} ${res.body}`);
  }
  return res.json("access_token");
}

// Runs once, before any VU iteration — tokens are handed to every VU via
// the returned `data` object rather than each VU fetching its own,
// which would multiply token requests by VU count for no reason and
// load-test Keycloak instead of the thing actually under test.
export function setup() {
  return {
    tokenLargeTenant: fetchToken("counselor.a", "password"),
    tokenSmallTenant: fetchToken("counselor.b", "password"),
  };
}

const ENDPOINTS = ["/api/v1/contacts", "/api/v1/deals", "/api/v1/tasks"];

function hitRandomEndpoint(token) {
  const path = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
  const res = http.get(`${BFF_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  check(res, { "status is 200": (r) => r.status === 200 });
  sleep(1);
}

export function largeTenant(data) {
  hitRandomEndpoint(data.tokenLargeTenant);
}

export function smallTenant(data) {
  hitRandomEndpoint(data.tokenSmallTenant);
}

export const options = {
  scenarios: {
    large_tenant: {
      executor: "constant-vus",
      exec: "largeTenant",
      vus: Number(__ENV.LARGE_TENANT_VUS || 20),
      duration: __ENV.DURATION || "30s",
    },
    small_tenant: {
      executor: "constant-vus",
      exec: "smallTenant",
      vus: Number(__ENV.SMALL_TENANT_VUS || 5),
      duration: __ENV.DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};
