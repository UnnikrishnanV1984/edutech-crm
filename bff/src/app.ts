import express, { type Express } from "express";

import { requireAuth } from "./middleware/auth.js";
import { errorHandler, notFoundHandler } from "./middleware/errorHandler.js";
import { requestContext } from "./middleware/requestContext.js";
import { stripForwardedHeaders } from "./middleware/stripForwardedHeaders.js";
import { createBackendProxy } from "./proxy.js";
import { healthRouter } from "./routes/health.js";

export function createApp(): Express {
  const app = express();
  app.disable("x-powered-by");

  // Must run before anything else — see stripForwardedHeaders.ts.
  app.use(stripForwardedHeaders);
  app.use(requestContext);

  app.use(healthRouter);

  app.use("/api/v1", requireAuth, createBackendProxy());

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
