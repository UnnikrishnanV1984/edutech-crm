import type { NextFunction, Request, Response } from "express";

import { errorEnvelope } from "../envelope.js";
import { ApiError, ERROR_CODES } from "../errors.js";

export function notFoundHandler(req: Request, res: Response): void {
  res.status(404).json(errorEnvelope(ERROR_CODES.NOT_FOUND, "Not found", req.requestId));
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function errorHandler(err: unknown, req: Request, res: Response, _next: NextFunction): void {
  if (err instanceof ApiError) {
    res
      .status(err.statusCode)
      .json(errorEnvelope(err.code, err.message, req.requestId, err.details));
    return;
  }
  req.log.error({ err }, "unhandled_error");
  res
    .status(500)
    .json(errorEnvelope(ERROR_CODES.INTERNAL_ERROR, "Internal server error", req.requestId));
}
