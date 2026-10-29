import { useState } from "react";

import { ApiRequestError } from "../api/client";
import { type Escalation, updateEscalation } from "../api/escalations";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { Spinner } from "../components/Spinner";
import { useUsers } from "../useUsers";

type Outcome = "resolve" | "reassign" | "snooze";

const OUTCOME_LABEL: Record<Outcome, string> = {
  resolve: "Contacted — close",
  reassign: "Reassign owner",
  snooze: "Snooze until…",
};

const SUBMIT_LABEL: Record<Outcome, string> = {
  resolve: "Resolve",
  reassign: "Reassign",
  snooze: "Snooze",
};

interface ResolveEscalationDrawerProps {
  escalation: Escalation;
  onClose: () => void;
  onUpdated: (escalation: Escalation) => void;
}

export function ResolveEscalationDrawer({
  escalation,
  onClose,
  onUpdated,
}: ResolveEscalationDrawerProps) {
  const { token } = useAuth();
  const users = useUsers();
  const [outcome, setOutcome] = useState<Outcome>("resolve");
  const [note, setNote] = useState("");
  const [reassignTo, setReassignTo] = useState("");
  const [snoozeUntil, setSnoozeUntil] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const reassignTargets = users.filter(
    (user) =>
      (user.role === "manager" || user.role === "admin") && user.id !== escalation.assigned_to,
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    if (outcome === "reassign" && !reassignTo) return;
    if (outcome === "snooze" && !snoozeUntil) return;

    setSubmitting(true);
    setError(undefined);
    try {
      const response = await updateEscalation(token, escalation.id, {
        ...(outcome === "resolve" && { status: "resolved" }),
        ...(outcome === "reassign" && { reassign_to: reassignTo }),
        ...(outcome === "snooze" && {
          status: "snoozed",
          snoozed_until: new Date(snoozeUntil).toISOString(),
        }),
        ...(note.trim() && { resolution_note: note.trim() }),
      });
      onUpdated(response.data);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't update the escalation");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="Resolve escalation" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
      >
        <div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Contact</div>
          <div style={{ marginTop: 4 }}>{escalation.contact_name ?? "—"}</div>
        </div>

        <div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            Breach detail
          </div>
          <div
            style={{
              marginTop: 4,
              padding: "var(--space-3)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--text-sm)",
            }}
          >
            <div>{escalation.reason ?? escalation.rule_name ?? "No further detail recorded"}</div>
            {escalation.rule_name && escalation.reason && (
              <div style={{ color: "var(--text-muted)", marginTop: 4 }}>{escalation.rule_name}</div>
            )}
          </div>
        </div>

        <div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Outcome</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            {(Object.keys(OUTCOME_LABEL) as Outcome[]).map((value) => (
              <label key={value} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  type="radio"
                  name="outcome"
                  checked={outcome === value}
                  onChange={() => setOutcome(value)}
                />
                <span style={{ fontSize: "var(--text-sm)" }}>{OUTCOME_LABEL[value]}</span>
              </label>
            ))}
          </div>
        </div>

        {outcome === "reassign" && (
          <label>
            Reassign to
            <div style={{ marginTop: 4 }}>
              <Select
                ariaLabel="Reassign to"
                value={reassignTo}
                onChange={setReassignTo}
                options={[
                  { value: "", label: "Select a manager…" },
                  ...reassignTargets.map((user) => ({
                    value: user.id,
                    label: user.full_name ?? user.email,
                  })),
                ]}
                triggerStyle={{ width: "100%" }}
              />
            </div>
          </label>
        )}

        {outcome === "snooze" && (
          <label>
            Snooze until
            <input
              required
              type="datetime-local"
              value={snoozeUntil}
              onChange={(event) => setSnoozeUntil(event.target.value)}
              style={{ display: "block", width: "100%", marginTop: 4 }}
            />
          </label>
        )}

        <label>
          Note
          <textarea
            rows={3}
            placeholder="What happened?"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>

        {error && (
          <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)", margin: 0 }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "auto" }}>
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={submitting}>
            {submitting ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> {SUBMIT_LABEL[outcome]}…
              </span>
            ) : (
              SUBMIT_LABEL[outcome]
            )}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
