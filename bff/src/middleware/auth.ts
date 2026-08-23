import type { NextFunction, Request, Response } from "express";

import { extractAppRole, verifyAccessToken } from "../auth/keycloak.js";
import { ApiError, ERROR_CODES } from "../errors.js";

export interface AuthContext {
  tenantId: string;
  userId: string;
  email: string;
  name?: string;
  role: string;
}

declare module "express-serve-static-core" {
  interface Request {
    auth?: AuthContext;
  }
}

// Required on every /api/v1 route (CLAUDE.md rule 3/7). Validates the
// caller's Keycloak access token against JWKS and populates req.auth —
// FastAPI never sees the token itself, only the headers proxy.ts derives
// from req.auth after this middleware succeeds.
export async function requireAuth(req: Request, _res: Response, next: NextFunction): Promise<void> {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    next(new ApiError(401, ERROR_CODES.UNAUTHORIZED, "Missing bearer token"));
    return;
  }
  const token = authHeader.slice("Bearer ".length);

  const claims = await verifyAccessToken(token).catch(() => undefined);
  if (!claims) {
    next(new ApiError(401, ERROR_CODES.UNAUTHORIZED, "Invalid or expired token"));
    return;
  }

  if (!claims.sub) {
    // Belt-and-suspenders: the realm's sub-explicit mapper (see
    // keycloak/README.md) should guarantee this, but a JWT library cast
    // doesn't enforce it at runtime — reject cleanly rather than forward
    // "undefined" as X-User-Id.
    next(new ApiError(401, ERROR_CODES.UNAUTHORIZED, "Token missing sub claim"));
    return;
  }
  if (!claims.tenant_id) {
    next(new ApiError(401, ERROR_CODES.UNAUTHORIZED, "Token missing tenant_id claim"));
    return;
  }
  if (!claims.email) {
    next(new ApiError(401, ERROR_CODES.UNAUTHORIZED, "Token missing email claim"));
    return;
  }
  const role = extractAppRole(claims.realm_access?.roles);
  if (!role) {
    next(new ApiError(401, ERROR_CODES.UNAUTHORIZED, "Token missing a recognized role"));
    return;
  }

  req.auth = {
    tenantId: claims.tenant_id,
    userId: claims.sub,
    email: claims.email,
    name: typeof claims.name === "string" ? claims.name : undefined,
    role,
  };
  next();
}
