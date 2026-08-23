function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function optional(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

export const config = {
  env: optional("ENVIRONMENT", "development"),
  logLevel: optional("LOG_LEVEL", "info"),
  port: Number(optional("BFF_PORT", "4000")),
  get backendBaseUrl(): string {
    return required("BACKEND_BASE_URL");
  },
};
