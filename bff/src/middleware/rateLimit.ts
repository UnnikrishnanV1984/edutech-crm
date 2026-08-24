import type { NextFunction, Request, Response } from "express";

import { config } from "../config/index.js";
import { ApiError, ERROR_CODES } from "../errors.js";
import { getConnectedRedisClient } from "../redisClient.js";

// API_CONVENTIONS.md §8 — primary rate-limit enforcement lives here, at
// the BFF, keyed by tenant_id, backed by Redis. FastAPI's own limiter
// (backend/app/core/rate_limit.py) only covers POST /webhooks/web, the
// one route that bypasses the BFF entirely — this is the general case
// for every authenticated /api/v1 request. Runs after requireAuth in
// app.ts's chain, so req.auth is always populated here.
export async function rateLimitByTenant(
  req: Request,
  _res: Response,
  next: NextFunction,
): Promise<void> {
  const tenantId = req.auth?.tenantId;
  if (!tenantId) {
    // requireAuth already rejected anything without a valid tenant_id
    // claim before this middleware runs — unreachable in practice, but
    // fail open rather than 500 on a defensive check.
    next();
    return;
  }

  try {
    const redis = await getConnectedRedisClient();
    if (!redis) {
      next();
      return;
    }
    const bucket = `ratelimit:${tenantId}:${Math.floor(Date.now() / 60_000)}`;
    const count = await redis.incr(bucket);
    if (count === 1) {
      await redis.expire(bucket, 60);
    }
    if (count > config.tenantRateLimitPerMinute) {
      next(new ApiError(429, ERROR_CODES.RATE_LIMITED, "Too many requests — try again shortly"));
      return;
    }
  } catch (err) {
    // Redis reachable but the command itself failed — same fail-open
    // stance as an unreachable Redis; this is defense-in-depth, not the
    // primary defense.
    req.log.error({ err }, "rate_limit_check_failed");
  }
  next();
}
