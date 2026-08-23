import pino from "pino";

import { config } from "./config/index.js";

// Only request_id/tenant_id/user_id are ever attached to a log line
// (CLAUDE.md rule 5) — never email, phone, or token/cookie values. Route
// handlers must log through req.log (a child logger, set by requestContext
// middleware), not this base logger, so that context is always present.
export const logger = pino({
  level: config.logLevel,
  formatters: {
    level(label) {
      return { level: label };
    },
  },
});
