import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    setupFiles: ["./src/__tests__/setup.ts"],
    // Default 5000ms was already tight for tests doing real RSA key
    // generation + local HTTP servers (auth.test.ts); rateLimit.test.ts
    // adds a real Redis round-trip on top, pushing occasional cold-start
    // runs past it. 10s gives headroom without masking a genuine hang.
    testTimeout: 10_000,
  },
});
