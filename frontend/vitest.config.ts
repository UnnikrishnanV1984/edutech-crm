import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/__tests__/setup.ts"],
    env: {
      VITE_KEYCLOAK_URL: "http://test-keycloak",
      VITE_KEYCLOAK_REALM: "test-realm",
      VITE_KEYCLOAK_CLIENT_ID: "web",
      VITE_BFF_BASE_URL: "http://test-bff",
      VITE_BACKEND_PUBLIC_URL: "http://test-backend",
    },
  },
});
