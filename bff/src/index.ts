import { createApp } from "./app.js";
import { config } from "./config/index.js";
import { logger } from "./logger.js";

const app = createApp();

app.listen(config.port, () => {
  logger.info({ port: config.port }, "bff_listening");
});
