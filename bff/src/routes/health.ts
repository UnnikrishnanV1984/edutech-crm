import { Router } from "express";

// /healthz is the only route exempt from auth/tenant handling — a plain
// liveness probe for k8s, no upstream calls.
export const healthRouter = Router();

healthRouter.get("/healthz", (_req, res) => {
  res.json({ status: "ok" });
});
