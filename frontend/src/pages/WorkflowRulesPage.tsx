import { useEffect, useState } from "react";

import {
  decideWorkflowRule,
  listWorkflowRules,
  type WorkflowRule,
} from "../api/workflowRules";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { useMe } from "../useMe";
import { CreateWorkflowRulePanel } from "./CreateWorkflowRulePanel";

const STATUS_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  draft: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
  pending_approval: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  active: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
  disabled: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
};

export function WorkflowRulesPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [rules, setRules] = useState<WorkflowRule[] | undefined>(undefined);
  const [showCreate, setShowCreate] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listWorkflowRules(token).then((response) => setRules(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role === "counselor") {
    return (
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
        <EmptyState headline="Managers and admins only" />
      </div>
    );
  }

  const isAdmin = me?.user.role === "admin";

  async function decide(rule: WorkflowRule, status: "active" | "disabled") {
    if (!token) return;
    setBusyId(rule.id);
    try {
      const response = await decideWorkflowRule(token, rule.id, status);
      setRules((current) => current?.map((r) => (r.id === rule.id ? response.data : r)));
    } finally {
      setBusyId(undefined);
    }
  }

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <h1 style={{ marginBottom: "var(--space-5)" }}>Workflow rules</h1>

      <Card
        title="Configured rules"
        action={
          <Button variant="primary" onClick={() => setShowCreate(true)}>
            + New rule
          </Button>
        }
      >
        {rules === undefined && <PageSpinner />}

        {rules && rules.length === 0 && <EmptyState headline="No workflow rules yet" />}

        {rules && rules.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "var(--space-2)" }}>Name</th>
                <th style={{ padding: "var(--space-2)" }}>Trigger</th>
                <th style={{ padding: "var(--space-2)" }}>Status</th>
                <th style={{ padding: "var(--space-2)" }}></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "var(--space-2)" }}>{rule.name}</td>
                  <td style={{ padding: "var(--space-2)" }}>{rule.trigger_type.replace("_", " ")}</td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <Badge
                      variant="chip"
                      label={rule.status.replace("_", " ")}
                      tone={STATUS_TONE[rule.status]}
                    />
                  </td>
                  <td style={{ padding: "var(--space-2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    {isAdmin && rule.status === "pending_approval" && (
                      <>
                        <Button
                          variant="text"
                          disabled={busyId === rule.id}
                          onClick={() => void decide(rule, "active")}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="text"
                          disabled={busyId === rule.id}
                          onClick={() => void decide(rule, "disabled")}
                        >
                          Reject
                        </Button>
                      </>
                    )}
                    {isAdmin && rule.status === "active" && (
                      <Button
                        variant="text"
                        disabled={busyId === rule.id}
                        onClick={() => void decide(rule, "disabled")}
                      >
                        Disable
                      </Button>
                    )}
                    {isAdmin && rule.status === "disabled" && (
                      <Button
                        variant="text"
                        disabled={busyId === rule.id}
                        onClick={() => void decide(rule, "active")}
                      >
                        Enable
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {showCreate && (
        <CreateWorkflowRulePanel
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}
