import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

import { exportJWK, generateKeyPair, SignJWT } from "jose";
import { createClient } from "redis";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

// GAP_FIXES_PLAN.md item 4 — requires a real, reachable Redis (the same
// docker-compose instance backend/worker use), matching backend's
// pytest.mark.skipif pattern for tests that need live infra. Skips
// cleanly rather than failing when Redis isn't reachable (e.g. a bare
// `npm test` with no docker-compose stack up).
const REDIS_URL = process.env.REDIS_URL_FOR_TESTS ?? "redis://localhost:6379/0";

async function redisReachable(): Promise<boolean> {
  const client = createClient({ url: REDIS_URL, socket: { connectTimeout: 500 } });
  client.on("error", () => {});
  try {
    await client.connect();
    await client.disconnect();
    return true;
  } catch {
    return false;
  }
}

const ISSUER = "http://test-issuer/realms/edutech-crm";
const CLIENT_ID = "web";

describe.runIf(await redisReachable())("rateLimitByTenant", () => {
  let jwksServer: Server;
  let jwksUrl: string;
  let backendServer: Server;
  let backendUrl: string;
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
    kid = "rate-limit-test-key";
    const jwk = await exportJWK(publicKey);
    jwk.kid = kid;
    jwk.alg = "RS256";
    jwk.use = "sig";

    jwksServer = createServer((_req, res) => {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ keys: [jwk] }));
    });
    await new Promise<void>((resolve) => jwksServer.listen(0, resolve));
    jwksUrl = `http://127.0.0.1:${(jwksServer.address() as AddressInfo).port}/certs`;

    backendServer = createServer((_req, res) => {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ data: { ok: true }, meta: { request_id: "stub" } }));
    });
    await new Promise<void>((resolve) => backendServer.listen(0, resolve));
    backendUrl = `http://127.0.0.1:${(backendServer.address() as AddressInfo).port}`;

    process.env.KEYCLOAK_ISSUER_URL = ISSUER;
    process.env.KEYCLOAK_JWKS_URL = jwksUrl;
    process.env.KEYCLOAK_CLIENT_ID = CLIENT_ID;
    process.env.BACKEND_BASE_URL = backendUrl;
    process.env.CORS_ORIGIN = "http://localhost:5173";
    process.env.REDIS_URL = REDIS_URL;
    process.env.TENANT_RATE_LIMIT_PER_MINUTE = "3";
  });

  afterAll(async () => {
    await new Promise((resolve) => jwksServer.close(resolve));
    await new Promise((resolve) => backendServer.close(resolve));
  });

  function tokenFor(tenantId: string, sub: string) {
    return signToken({
      sub,
      tenant_id: tenantId,
      email: `${sub}@example.test`,
      realm_access: { roles: ["counselor"] },
    });
  }

  it("429s once a tenant exceeds its per-minute budget", async () => {
    const tenantId = `rl-test-a-${Date.now()}`;
    const token = await tokenFor(tenantId, "sub-rl-a");
    const { createApp } = await import("../app.js");
    const app = createApp();

    const responses = [];
    for (let i = 0; i < 4; i++) {
      responses.push(
        await request(app).get("/api/v1/me").set("Authorization", `Bearer ${token}`),
      );
    }

    const fourth = responses.at(3)!;
    expect(responses.slice(0, 3).every((r) => r.status === 200)).toBe(true);
    expect(fourth.status).toBe(429);
    expect(fourth.body.error.code).toBe("RATE_LIMITED");
  });

  it("does not let one tenant's usage affect another tenant's budget", async () => {
    const tenantA = `rl-test-b-${Date.now()}`;
    const tenantB = `rl-test-c-${Date.now()}`;
    const tokenA = await tokenFor(tenantA, "sub-rl-b");
    const tokenB = await tokenFor(tenantB, "sub-rl-c");
    const { createApp } = await import("../app.js");
    const app = createApp();

    for (let i = 0; i < 3; i++) {
      await request(app).get("/api/v1/me").set("Authorization", `Bearer ${tokenA}`);
    }
    // Tenant A is now at its limit — tenant B should be unaffected.
    const response = await request(app).get("/api/v1/me").set("Authorization", `Bearer ${tokenB}`);
    expect(response.status).toBe(200);
  });
});
