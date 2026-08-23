import { randomUUID } from "node:crypto";

import type { NextFunction, Request, Response } from "express";

import { logger } from "../logger.js";

declare module "express-serve-static-core" {
  interface Request {
    requestId: string;
    log: typeof logger;
  }
}

export function requestContext(req: Request, res: Response, next: NextFunction): void {
  const requestId = (req.headers["x-request-id"] as string | undefined) || randomUUID();
  req.requestId = requestId;
  req.log = logger.child({ request_id: requestId });
  res.setHeader("X-Request-Id", requestId);

  const start = Date.now();
  res.on("finish", () => {
    req.log.info(
      {
        method: req.method,
        path: req.path,
        status_code: res.statusCode,
        duration_ms: Date.now() - start,
      },
      "request_completed",
    );
  });

  next();
}
