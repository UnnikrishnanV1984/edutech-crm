import express, { type Express } from "express";

import { errorHandler, notFoundHandler } from "./middleware/errorHandler.js";
import { requestContext } from "./middleware/requestContext.js";
import { healthRouter } from "./routes/health.js";

export function createApp(): Express {
  const app = express();
  app.disable("x-powered-by");
  app.use(requestContext);

  app.use(healthRouter);

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
