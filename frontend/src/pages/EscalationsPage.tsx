import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listEscalations, type Escalation, type EscalationStatus } from "../api/escalations";
import { getEscalationSummary, type EscalationSummary } from "../api/reports";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { useMe } from "../useMe";
import { ResolveEscalationDrawer } from "./ResolveEscalationDrawer";

const STATUS_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  open: { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" },
  acknowledged: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  resolved: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
  reassigned: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
  snoozed: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
};

// Friendly fallback when the escalation carries no freeform reason of its
// own (true for every auto-generated source — only "manual" ever sets
// escalation.reason) — same source->label mapping the page used before
// this rebuild, just relabeled "Reason" to match the wireframe.
const SOURCE_FALLBACK: Record<string, string> = {
  sla_breach: "SLA breach",
  workflow_failure: "Automation failure",
  rule_triggered: "Workflow rule",
  manual: "Manual",
};

const STATUS_FILTERS: { value: EscalationStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "resolved", label: "Resolved" },
];

function Chip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-medium)",
        padding: "4px 10px",
        borderRadius: 999,
        border: `1px solid ${selected ? "var(--text-h)" : "var(--border)"}`,
        background: "transparent",
        color: selected ? "var(--text-h)" : "var(--text-muted)",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

function KpiBox({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <Card>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{label}</div>
      <div
        style={{
          fontSize: "var(--text-2xl)",
          fontWeight: "var(--weight-semibold)",
          marginTop: 8,
          color: accent ? "var(--accent)" : "var(--text-h)",
        }}
      >
        {value}
      </div>
    </Card>
  );
}

export function EscalationsPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<EscalationStatus>("open");
  const [escalations, setEscalations] = useState<Escalation[] | undefined>(undefined);
  const [summary, setSummary] = useState<EscalationSummary | undefined>(undefined);
  const [resolving, setResolving] = useState<Escalation | undefined>(undefined);

  function load() {
    if (!token) return;
    listEscalations(token, { status: statusFilter }).then((response) =>
      setEscalations(response.data),
    );
  }

  function loadSummary() {
    if (!token) return;
    getEscalationSummary(token).then((response) => setSummary(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, statusFilter]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadSummary, [token]);

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

  function handleUpdated(updated: Escalation) {
    setResolving(undefined);
    setEscalations((current) => current?.filter((e) => e.id !== updated.id));
    loadSummary();
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>Escalations</h1>
        <Badge
          label={`${String(summary?.open ?? 0).padStart(2, "0")} open`}
          tone={{ bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" }}
        />
        <div style={{ flex: 1 }} />
        {STATUS_FILTERS.map((filter) => (
          <Chip
            key={filter.value}
            label={filter.label}
            selected={statusFilter === filter.value}
            onClick={() => setStatusFilter(filter.value)}
          />
        ))}
      </div>

      <div className="grid-4col" style={{ marginBottom: "var(--space-5)" }}>
        <KpiBox label="Open" value={String(summary?.open ?? 0).padStart(2, "0")} />
        <KpiBox
          label="Breaching within 1h"
          value={String(summary?.breaching_within_1h ?? 0).padStart(2, "0")}
          accent
        />
        <KpiBox
          label="Avg time to resolve"
          value={`${Math.round((summary?.avg_resolve_minutes ?? 0) / 60)}h`}
        />
        <KpiBox label="Reopened" value={String(summary?.reopened ?? 0).padStart(2, "0")} />
      </div>

      <Card>
        {escalations === undefined && <PageSpinner />}

        {escalations && escalations.length === 0 && (
          <EmptyState
            headline="Nothing here"
            subtext={`No ${STATUS_FILTERS.find((f) => f.value === statusFilter)?.label.toLowerCase()} escalations right now.`}
          />
        )}

        {escalations && escalations.length > 0 && (
          <div className="table-scroll">
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "var(--space-2)" }}>Contact / deal</th>
                <th style={{ padding: "var(--space-2)" }}>Reason</th>
                <th style={{ padding: "var(--space-2)" }}>Rule</th>
                <th style={{ padding: "var(--space-2)" }}>Owner</th>
                <th style={{ padding: "var(--space-2)" }}>Status</th>
                <th style={{ padding: "var(--space-2)" }}>Opened</th>
                <th style={{ padding: "var(--space-2)" }}></th>
              </tr>
            </thead>
            <tbody>
              {escalations.map((escalation) => (
                <tr
                  key={escalation.id}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    background:
                      escalation.status === "open" && escalation.source === "sla_breach"
                        ? "var(--danger-bg)"
                        : undefined,
                  }}
                >
                  <td style={{ padding: "var(--space-2)" }}>
                    {escalation.contact_id ? (
                      <button
                        type="button"
                        onClick={() => navigate(`/contacts/${escalation.contact_id}`)}
                        style={{
                          background: "none",
                          border: "none",
                          padding: 0,
                          color: "var(--text-h)",
                          textDecoration: "underline",
                          cursor: "pointer",
                        }}
                      >
                        {escalation.contact_name ?? "View contact"}
                      </button>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <Badge
                      label={escalation.reason ?? SOURCE_FALLBACK[escalation.source] ?? "Escalation"}
                      tone={escalation.source === "sla_breach" ? STATUS_TONE.open : undefined}
                    />
                  </td>
                  <td style={{ padding: "var(--space-2)", color: "var(--text-muted)" }}>
                    {escalation.rule_name ?? "—"}
                  </td>
                  <td style={{ padding: "var(--space-2)" }}>{escalation.assigned_to_name ?? "—"}</td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <Badge label={escalation.status} tone={STATUS_TONE[escalation.status]} />
                  </td>
                  <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: 13 }}>
                    {new Date(escalation.opened_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "var(--space-2)", textAlign: "right" }}>
                    {escalation.status !== "resolved" && (
                      <Chip label="Resolve" onClick={() => setResolving(escalation)} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </Card>

      {resolving && (
        <ResolveEscalationDrawer
          escalation={resolving}
          onClose={() => setResolving(undefined)}
          onUpdated={handleUpdated}
        />
      )}
    </div>
  );
}
