import { createClient, type RedisClientType } from "redis";

import { config } from "./config/index.js";
import { logger } from "./logger.js";

let client: RedisClientType | undefined;
let retryNotBefore = 0;

function getClient(): RedisClientType {
  if (!client) {
    client = createClient({
      url: config.redisUrl,
      // No auto-reconnect loop — this is a best-effort, defense-in-depth
      // check (API_CONVENTIONS.md §8), not a hard dependency.
      // getConnectedRedisClient's own retryNotBefore cooldown is what
      // actually paces reconnection attempts.
      socket: { reconnectStrategy: false, connectTimeout: 1000 },
    });
    client.on("error", () => {
      // Swallowed deliberately — every caller already wraps its use of
      // this client in try/catch and fails open; an unhandled 'error'
      // listener would otherwise crash the process on a dropped
      // connection (node-redis's default EventEmitter behavior).
    });
  }
  return client;
}

const CONNECT_RACE_TIMEOUT_MS = 500;

/** node-redis's own socket.connectTimeout doesn't reliably bound a
 * failed DNS lookup (observed multi-second stalls resolving the
 * docker-compose-internal "redis" hostname from outside a container,
 * e.g. running bff's tests directly on the host) — race it against an
 * explicit timer instead so a bad hostname fails fast like a refused
 * connection does. */
async function connectWithTimeout(redis: RedisClientType, ms: number): Promise<void> {
  const connectPromise = redis.connect();
  // If connect() eventually settles after we've already given up on it
  // below, nothing else awaits this promise — attach a no-op catch so
  // that doesn't surface as an unhandled rejection.
  void connectPromise.catch(() => {});

  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("redis connect timeout")), ms);
    connectPromise.then(
      () => {
        clearTimeout(timer);
        resolve();
      },
      (err: unknown) => {
        clearTimeout(timer);
        reject(err instanceof Error ? err : new Error(String(err)));
      },
    );
  });
}

/** Returns a connected client, or undefined if Redis is currently
 * unreachable — callers must fail open on undefined, never throw.
 * Cools down for 10s after a failed attempt so an outage doesn't turn
 * into a connect-timeout tax on every single request. */
export async function getConnectedRedisClient(): Promise<RedisClientType | undefined> {
  const redis = getClient();
  if (redis.isOpen) {
    return redis;
  }
  if (Date.now() < retryNotBefore) {
    return undefined;
  }
  try {
    await connectWithTimeout(redis, CONNECT_RACE_TIMEOUT_MS);
    return redis;
  } catch (err) {
    retryNotBefore = Date.now() + 10_000;
    logger.warn({ err }, "redis_connect_failed");
    return undefined;
  }
}
