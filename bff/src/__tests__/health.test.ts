import request from "supertest";
import { describe, expect, it } from "vitest";

import { createApp } from "../app.js";

describe("GET /healthz", () => {
  it("returns 200 ok", async () => {
    const app = createApp();
    const response = await request(app).get("/healthz");
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ status: "ok" });
  });

  it("sets X-Request-Id", async () => {
    const app = createApp();
    const response = await request(app).get("/healthz");
    expect(response.headers["x-request-id"]).toBeTruthy();
  });
});

describe("unmatched route", () => {
  it("returns the standard NOT_FOUND envelope", async () => {
    const app = createApp();
    const response = await request(app).get("/does-not-exist");
    expect(response.status).toBe(404);
    expect(response.body.error.code).toBe("NOT_FOUND");
    expect(response.body.meta.request_id).toBeTruthy();
  });
});
