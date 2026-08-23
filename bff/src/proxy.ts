import type { Request } from "express";
import { createProxyMiddleware } from "http-proxy-middleware";

import { config } from "./config/index.js";

// Sets the headers FastAPI trusts (API_CONVENTIONS.md §1) from req.auth —
// the validated output of requireAuth, which always runs first on every
// proxied route. Never reads these values from the inbound request itself
// (stripForwardedHeaders has already deleted any client-supplied copies
// regardless, but this only ever consults req.auth, never req.headers, as
// a second independent guarantee).
export function createBackendProxy() {
  return createProxyMiddleware({
    target: config.backendBaseUrl,
    changeOrigin: true,
    // Express strips the "/api/v1" mount prefix from req.url before this
    // middleware sees it (e.g. "/api/v1/me" arrives as "/me") — restore it
    // so FastAPI's routes, which are registered at /api/v1/..., actually
    // match. Confirmed live: without this, every proxied call 404'd
    // against FastAPI while looking completely fine at the BFF layer.
    pathRewrite: (path) => `/api/v1${path}`,
    on: {
      proxyReq: (proxyReq, req) => {
        const request = req as Request;
        const auth = request.auth;
        if (!auth) {
          // Unreachable in practice — requireAuth always runs first and
          // either populates req.auth or short-circuits with an error
          // response before this middleware is reached.
          proxyReq.destroy(new Error("proxy reached without auth context"));
          return;
        }
        proxyReq.setHeader("X-Tenant-Id", auth.tenantId);
        proxyReq.setHeader("X-User-Id", auth.userId);
        proxyReq.setHeader("X-User-Email", auth.email);
        if (auth.name) {
          proxyReq.setHeader("X-User-Name", auth.name);
        }
        proxyReq.setHeader("X-User-Role", auth.role);
        proxyReq.setHeader("X-Request-Id", request.requestId);
      },
    },
  });
}
