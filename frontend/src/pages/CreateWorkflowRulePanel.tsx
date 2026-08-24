import { useState } from "react";

import {
  createWorkflowRule,
  type ActionType,
  type TriggerType,
  type WorkflowRule,
} from "../api/workflowRules";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";

interface CreateWorkflowRulePanelProps {
  onClose: () => void;
  onCreated: (rule: WorkflowRule) => void;
}

const TRIGGERS: { value: TriggerType; label: string }[] = [
  { value: "lead_created", label: "A new lead is created" },
  { value: "stage_changed", label: "A deal's stage changes" },
  { value: "task_overdue", label: "A task becomes overdue" },
  { value: "elapsed_time", label: "Time elapses since stage entry" },
];

const ACTIONS: { value: ActionType; label: string }[] = [
  { value: "assign_round_robin", label: "Assign round-robin" },
  { value: "create_task", label: "Create a follow-up task" },
  { value: "change_stage", label: "Change the deal's stage" },
  { value: "notify_manager", label: "Notify the manager" },
  { value: "raise_escalation", label: "Raise an escalation" },
  { value: "send_message", label: "Send a message (not yet available)" },
];

export function CreateWorkflowRulePanel({ onClose, onCreated }: CreateWorkflowRulePanelProps) {
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState<TriggerType>("lead_created");
  const [elapsedMinutes, setElapsedMinutes] = useState(1440);
  const [actionType, setActionType] = useState<ActionType>("notify_manager");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const response = await createWorkflowRule(token, {
        name,
        trigger_type: triggerType,
        trigger_config:
          triggerType === "elapsed_time"
            ? { since: "stage_entered_at", minutes: elapsedMinutes }
            : {},
        actions: [{ type: actionType, config: {} }],
      });
      onCreated(response.data);
    } catch {
      setError("Couldn't create rule — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="New workflow rule" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <label>
          Name*
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          When*
          <select
            value={triggerType}
            onChange={(event) => setTriggerType(event.target.value as TriggerType)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {TRIGGERS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        {triggerType === "elapsed_time" && (
          <label>
            Minutes since the deal entered its current stage*
            <input
              required
              type="number"
              min={1}
              value={elapsedMinutes}
              onChange={(event) => setElapsedMinutes(Number(event.target.value))}
              style={{ display: "block", width: "100%", marginTop: 4 }}
            />
          </label>
        )}
        <label>
          Then*
          <select
            value={actionType}
            onChange={(event) => setActionType(event.target.value as ActionType)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {ACTIONS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>
        <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
          One action per rule for now — a multi-step rule builder is a follow-up.
        </p>
        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create rule"}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
