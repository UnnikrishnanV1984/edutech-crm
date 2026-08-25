import { useState } from "react";

import { ApiRequestError } from "../api/client";
import { raiseEscalation } from "../api/escalations";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";

const SLA_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  breached: { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" },
  at_risk: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  on_track: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
};

function slaLabel(state: string | null): string {
  if (state === null) return "No SLA yet";
  return state.replace("_", " ");
}

interface SlaCardProps {
  dealId: string | null;
  slaState: "on_track" | "at_risk" | "breached" | null;
  targetAt: string | null;
  targetMinutes: number | null;
}

export function SlaCard({ dealId, slaState, targetAt, targetMinutes }: SlaCardProps) {
  const { token } = useAuth();
  const [showEscalate, setShowEscalate] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [raised, setRaised] = useState(false);

  let elapsedMinutes: number | undefined;
  let progressPct: number | undefined;
  if (targetAt && targetMinutes) {
    // Display-only progress bar, not reconciliation identity — safe to
    // read the clock during render here (same convention as
    // TasksSection.tsx's own overdue flag).
    // oxlint-disable-next-line react/purity
    const minutesRemaining = (new Date(targetAt).getTime() - Date.now()) / 60_000;
    elapsedMinutes = Math.max(0, Math.round(targetMinutes - minutesRemaining));
    progressPct = Math.min(100, Math.max(0, (elapsedMinutes / targetMinutes) * 100));
  }

  async function handleEscalate(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !dealId || !reason.trim()) return;
    setSubmitting(true);
    setError(undefined);
    try {
      await raiseEscalation(token, { deal_id: dealId, reason: reason.trim() });
      setRaised(true);
      setShowEscalate(false);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't raise escalation");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: "var(--weight-semibold)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--text-muted)",
          }}
        >
          SLA
        </span>
        <div style={{ flex: 1 }} />
        <Badge label={slaLabel(slaState)} tone={slaState ? SLA_TONE[slaState] : undefined} />
      </div>

      {!dealId && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", margin: "var(--space-3) 0 0" }}>
          No active deal to track.
        </p>
      )}

      {dealId && elapsedMinutes !== undefined && progressPct !== undefined && targetMinutes && (
        <div style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)" }}>
            <span style={{ color: "var(--text-muted)" }}>Elapsed</span>
            <span>{elapsedMinutes} min</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)" }}>
            <span style={{ color: "var(--text-muted)" }}>Target</span>
            <span>{targetMinutes} min</span>
          </div>
          <div style={{ height: 8, background: "var(--surface-hover)", borderRadius: 999 }}>
            <div
              style={{
                width: `${progressPct}%`,
                height: 8,
                borderRadius: 999,
                background: slaState === "breached" ? "var(--danger)" : "var(--accent)",
              }}
            />
          </div>
        </div>
      )}

      {dealId && !raised && !showEscalate && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <Button variant="secondary" onClick={() => setShowEscalate(true)}>
            Escalate
          </Button>
        </div>
      )}

      {raised && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--success)", margin: "var(--space-3) 0 0" }}>
          Escalation raised — your manager has been notified.
        </p>
      )}

      {showEscalate && (
        <form
          onSubmit={(event) => {
            void handleEscalate(event);
          }}
          style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
        >
          <textarea
            required
            autoFocus
            rows={3}
            placeholder="What's blocking this? (e.g. waiting on a document, pricing exception needed)"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            style={{ width: "100%" }}
          />
          {error && (
            <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)", margin: 0 }}>
              {error}
            </p>
          )}
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button variant="primary" type="submit" disabled={submitting || !reason.trim()}>
              {submitting ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Spinner size={12} /> Raising…
                </span>
              ) : (
                "Raise escalation"
              )}
            </Button>
            <Button variant="text" type="button" disabled={submitting} onClick={() => setShowEscalate(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
