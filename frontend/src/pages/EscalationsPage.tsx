import { useEffect, useState } from "react";

import { listEscalations, updateEscalation, type Escalation } from "../api/escalations";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { useMe } from "../useMe";

const STATUS_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  open: { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" },
  acknowledged: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  resolved: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
  reassigned: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
};

const SOURCE_LABELS: Record<string, string> = {
  sla_breach: "SLA breach",
  workflow_failure: "Automation failure",
  rule_triggered: "Workflow rule",
  manual: "Manually raised",
};

export function EscalationsPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [escalations, setEscalations] = useState<Escalation[] | undefined>(undefined);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listEscalations(token).then((response) => setEscalations(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role === "counselor") {
    return (
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
        <EmptyState
          headline="Managers and admins only"
          subtext="You can raise an escalation from a deal, but the queue itself is a manager view."
        />
      </div>
    );
  }

  async function act(escalation: Escalation, status: "acknowledged" | "resolved") {
    if (!token) return;
    setBusyId(escalation.id);
    try {
      const response = await updateEscalation(token, escalation.id, { status });
      setEscalations((current) =>
        current?.map((e) => (e.id === escalation.id ? response.data : e)),
      );
    } finally {
      setBusyId(undefined);
    }
  }

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <h1 style={{ marginBottom: "var(--space-5)" }}>Escalations</h1>

      <Card>
        {escalations === undefined && <PageSpinner />}

        {escalations && escalations.length === 0 && (
          <EmptyState headline="Nothing escalated" subtext="Open escalations assigned to you will show up here." />
        )}

        {escalations && escalations.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "var(--space-2)" }}>Source</th>
                <th style={{ padding: "var(--space-2)" }}>Status</th>
                <th style={{ padding: "var(--space-2)" }}>Opened</th>
                <th style={{ padding: "var(--space-2)" }}></th>
              </tr>
            </thead>
            <tbody>
              {escalations.map((escalation) => (
                <tr key={escalation.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "var(--space-2)" }}>{SOURCE_LABELS[escalation.source]}</td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <Badge variant="chip" label={escalation.status} tone={STATUS_TONE[escalation.status]} />
                  </td>
                  <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: 13 }}>
                    {new Date(escalation.opened_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "var(--space-2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    {escalation.status === "open" && (
                      <Button
                        variant="text"
                        disabled={busyId === escalation.id}
                        onClick={() => void act(escalation, "acknowledged")}
                      >
                        Acknowledge
                      </Button>
                    )}
                    {escalation.status === "acknowledged" && (
                      <Button
                        variant="text"
                        disabled={busyId === escalation.id}
                        onClick={() => void act(escalation, "resolved")}
                      >
                        Resolve
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
