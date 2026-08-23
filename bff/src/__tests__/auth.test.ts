import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

import { exportJWK, generateKeyPair, SignJWT } from "jose";
import request from "supertest";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

// A from-scratch local JWKS + stub upstream, standing in for Keycloak +
// FastAPI, so this suite runs in CI without live infra. Mirrors exactly
// what was hand-verified against real Keycloak/Postgres/FastAPI/BFF
// containers during development (DEVELOPMENT_PLAN.md §7 criteria 6-9):
// forged tenant/role headers from the client must never reach the
// upstream, and a missing/invalid/incomplete token must 401 before any
// proxying happens.

const ISSUER = "http://test-issuer/realms/edutech-crm";
const CLIENT_ID = "web";

let jwksServer: Server;
let jwksUrl: string;
let backendServer: Server;
let backendUrl: string;
let lastBackendHeaders: Record<string, string | string[] | undefined> = {};
let lastBackendUrl = "";
let lastBackendMethod = "";
let lastBackendBody = "";
let privateKey: Awaited<ReturnType<typeof generateKeyPair>>["privateKey"];
let kid: string;

async function signToken(claims: Record<string, unknown>): Promise<string> {
  return new SignJWT(claims)
    .setProtectedHeader({ alg: "RS256", kid })
    .setIssuedAt()
    .setIssuer(ISSUER)
    .setAudience(CLIENT_ID)
    .setExpirationTime("5m")
    .sign(privateKey);
}

beforeAll(async () => {
  const { publicKey, privateKey: sk } = await generateKeyPair("RS256");
  privateKey = sk;
  kid = "test-key-1";
  const jwk = await exportJWK(publicKey);
  jwk.kid = kid;
  jwk.alg = "RS256";
  jwk.use = "sig";

  jwksServer = createServer((_req, res) => {
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ keys: [jwk] }));
  });
  await new Promise<void>((resolve) => jwksServer.listen(0, resolve));
  const jwksPort = (jwksServer.address() as AddressInfo).port;
  jwksUrl = `http://127.0.0.1:${jwksPort}/certs`;

  backendServer = createServer((req, res) => {
    lastBackendHeaders = req.headers;
    lastBackendUrl = req.url ?? "";
    lastBackendMethod = req.method ?? "";
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => {
      lastBackendBody = Buffer.concat(chunks).toString("utf8");
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ data: { ok: true }, meta: { request_id: "stub" } }));
    });
  });
  await new Promise<void>((resolve) => backendServer.listen(0, resolve));
  const backendPort = (backendServer.address() as AddressInfo).port;
  backendUrl = `http://127.0.0.1:${backendPort}`;

  process.env.KEYCLOAK_ISSUER_URL = ISSUER;
  process.env.KEYCLOAK_JWKS_URL = jwksUrl;
  process.env.KEYCLOAK_CLIENT_ID = CLIENT_ID;
  process.env.BACKEND_BASE_URL = backendUrl;
});

afterAll(async () => {
  await new Promise((resolve) => jwksServer.close(resolve));
  await new Promise((resolve) => backendServer.close(resolve));
});

afterEach(() => {
  lastBackendHeaders = {};
  lastBackendUrl = "";
  lastBackendMethod = "";
  lastBackendBody = "";
});

const TENANT_A = "a1111111-1111-1111-1111-111111111111";
const TENANT_B = "b2222222-2222-2222-2222-222222222222";

function validClaims(overrides: Record<string, unknown> = {}) {
  return {
    sub: "kc-sub-a",
    tenant_id: TENANT_A,
    email: "counselor.a@example.test",
    name: "Asha Rao",
    realm_access: { roles: ["counselor"] },
    ...overrides,
  };
}

describe("requireAuth + proxy", () => {
  it("401s with no Authorization header", async () => {
    const { createApp } = await import("../app.js");
    const response = await request(createApp()).get("/api/v1/me");
    expect(response.status).toBe(401);
    expect(response.body.error.code).toBe("UNAUTHORIZED");
  });

  it("401s on a garbage token", async () => {
    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", "Bearer not-a-real-jwt");
    expect(response.status).toBe(401);
  });

  it("401s on a token signed by an unknown key", async () => {
    const { privateKey: otherKey } = await generateKeyPair("RS256");
    const token = await new SignJWT(validClaims())
      .setProtectedHeader({ alg: "RS256", kid: "wrong-key" })
      .setIssuedAt()
      .setIssuer(ISSUER)
      .setAudience(CLIENT_ID)
      .setExpirationTime("5m")
      .sign(otherKey);

    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", `Bearer ${token}`);
    expect(response.status).toBe(401);
  });

  it("401s when tenant_id claim is missing", async () => {
    const token = await signToken(validClaims({ tenant_id: undefined }));
    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", `Bearer ${token}`);
    expect(response.status).toBe(401);
  });

  it("401s when sub claim is missing", async () => {
    const token = await signToken(validClaims({ sub: undefined }));
    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", `Bearer ${token}`);
    expect(response.status).toBe(401);
  });

  it("401s when no recognized role is present", async () => {
    const token = await signToken(
      validClaims({ realm_access: { roles: ["default-roles-edutech-crm"] } }),
    );
    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", `Bearer ${token}`);
    expect(response.status).toBe(401);
  });

  it("forwards the correct headers to the backend on a valid token", async () => {
    const token = await signToken(validClaims());
    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", `Bearer ${token}`);

    expect(response.status).toBe(200);
    expect(lastBackendHeaders["x-tenant-id"]).toBe(TENANT_A);
    expect(lastBackendHeaders["x-user-id"]).toBe("kc-sub-a");
    expect(lastBackendHeaders["x-user-email"]).toBe("counselor.a@example.test");
    expect(lastBackendHeaders["x-user-role"]).toBe("counselor");
  });

  it("ignores a client-forged X-Tenant-Id and X-User-Role", async () => {
    const token = await signToken(validClaims());
    const { createApp } = await import("../app.js");
    const response = await request(createApp())
      .get("/api/v1/me")
      .set("Authorization", `Bearer ${token}`)
      .set("X-Tenant-Id", TENANT_B)
      .set("X-User-Role", "admin");

    expect(response.status).toBe(200);
    // The forged values must never reach the backend — only the token's.
    expect(lastBackendHeaders["x-tenant-id"]).toBe(TENANT_A);
    expect(lastBackendHeaders["x-user-role"]).toBe("counselor");
  });

  it("forwards the correct path to the backend (/api/v1 prefix preserved)", async () => {
    const token = await signToken(validClaims());
    const { createApp } = await import("../app.js");
    await request(createApp()).get("/api/v1/me").set("Authorization", `Bearer ${token}`);
    // If pathRewrite regresses, the backend receives "/me" instead of
    // "/api/v1/me" — this was a real bug caught during manual E2E testing.
    expect(lastBackendUrl).toBe("/api/v1/me");
  });

  it("proxies a POST body intact to a resource path (contacts, deals, ...)", async () => {
    // Phase 0 only ever exercised GET /api/v1/me — no request body, no
    // resource path beyond /me. Every Phase 1 endpoint (contacts, deals,
    // tasks, documents) needs POST/PATCH with a JSON body to survive the
    // proxy unmodified; there's no express.json() in app.ts, so the raw
    // request stream should pass straight through http-proxy-middleware.
    const token = await signToken(validClaims());
    const { createApp } = await import("../app.js");
    const payload = { full_name: "Asha Rao", email: "asha@example.test", lead_source: "web" };
    const response = await request(createApp())
      .post("/api/v1/contacts")
      .set("Authorization", `Bearer ${token}`)
      .send(payload);

    expect(response.status).toBe(200);
    expect(lastBackendMethod).toBe("POST");
    expect(lastBackendUrl).toBe("/api/v1/contacts");
    expect(JSON.parse(lastBackendBody)).toEqual(payload);
    expect(lastBackendHeaders["content-type"]).toContain("application/json");
  });

  it("proxies a PATCH body intact (used by the deal stage-transition endpoint)", async () => {
    const token = await signToken(validClaims());
    const { createApp } = await import("../app.js");
    const payload = { stage_id: "33333333-0000-0000-0000-000000000001" };
    const response = await request(createApp())
      .patch("/api/v1/deals/44444444-0000-0000-0000-000000000001")
      .set("Authorization", `Bearer ${token}`)
      .send(payload);

    expect(response.status).toBe(200);
    expect(lastBackendMethod).toBe("PATCH");
    expect(lastBackendUrl).toBe("/api/v1/deals/44444444-0000-0000-0000-000000000001");
    expect(JSON.parse(lastBackendBody)).toEqual(payload);
  });
});
