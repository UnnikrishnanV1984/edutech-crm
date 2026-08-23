import type { NextFunction, Request, Response } from "express";

import { FORWARDED_AUTH_HEADERS } from "../auth/forwardedHeaders.js";

// Runs before auth on every request, unconditionally — so even a route
// added later without going through the auth middleware still can't have
// a client-forged X-Tenant-Id/X-User-* header reach FastAPI (CLAUDE.md
// rule 7). Defense in depth: auth.ts is what actually sets these from
// validated token claims, but this must run first regardless.
export function stripForwardedHeaders(req: Request, _res: Response, next: NextFunction): void {
  for (const header of FORWARDED_AUTH_HEADERS) {
    delete req.headers[header];
  }
  next();
}
