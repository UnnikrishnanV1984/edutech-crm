import { useEffect, useState } from "react";

import {
  decideWorkflowRule,
  listWorkflowRules,
  listWorkflowRuns,
  type WorkflowRule,
  type WorkflowRun,
} from "../api/workflowRules";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { useMe } from "../useMe";
import { WorkflowRuleBuilder } from "./WorkflowRuleBuilder";
import { WorkflowRunHistoryPanel } from "./WorkflowRunHistoryPanel";

const STATUS_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  draft: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
  pending_approval: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  active: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
  disabled: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
};

const TRIGGER_LABELS: Record<string, string> = {
  lead_created: "Lead created",
  stage_changed: "Stage entry",
  task_overdue: "Task overdue",
  elapsed_time: "Elapsed time",
};

const ACTION_LABELS: Record<string, string> = {
  assign_round_robin: "Assign",
  assign_by_territory: "Assign",
  create_task: "Task",
  change_stage: "Change stage",
  notify_manager: "Notify",
  raise_escalation: "Escalate",
  send_message: "Message",
};

const RUN_STATUS_HEIGHT: Record<string, string> = {
  success: "100%",
  failed: "30%",
  retrying: "60%",
  skipped_unavailable: "45%",
};

export function WorkflowRulesPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [rules, setRules] = useState<WorkflowRule[] | undefined>(undefined);
  const [recentRuns, setRecentRuns] = useState<WorkflowRun[]>([]);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);
  const [selectedRuleId, setSelectedRuleId] = useState<string | undefined>(undefined);
  const [creating, setCreating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  function load() {
    if (!token) return;
    listWorkflowRules(token).then((response) => setRules(response.data));
    listWorkflowRuns(token, { page_size: 100 }).then((response) => setRecentRuns(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role === "counselor") {
    return (
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "var(--space-6)" }}>
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

  const lastRunByRule = new Map<string, WorkflowRun>();
  for (const run of recentRuns) {
    if (!lastRunByRule.has(run.workflow_rule_id)) {
      lastRunByRule.set(run.workflow_rule_id, run);
    }
  }

  const activeCount = rules?.filter((r) => r.status === "active").length ?? 0;
  const pausedCount = rules?.filter((r) => r.status === "disabled").length ?? 0;
  const selectedRule = rules?.find((r) => r.id === selectedRuleId);

  function closeBuilder() {
    setSelectedRuleId(undefined);
    setCreating(false);
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>Workflow rules</h1>
        <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
          {String(activeCount).padStart(2, "0")} active · {String(pausedCount).padStart(2, "0")} paused
        </span>
        <div style={{ flex: 1 }} />
        <Button variant="secondary" onClick={() => setShowHistory(true)}>
          Run history
        </Button>
        <Button
          variant="primary"
          onClick={() => {
            setSelectedRuleId(undefined);
            setCreating(true);
          }}
        >
          + New rule
        </Button>
      </div>

      <div className="split-row">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Card>
            {rules === undefined && <PageSpinner />}

            {rules && rules.length === 0 && <EmptyState headline="No workflow rules yet" />}

            {rules && rules.length > 0 && (
              <div className="table-scroll">
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                    <th style={{ padding: "var(--space-2)" }}>Rule</th>
                    <th style={{ padding: "var(--space-2)" }}>Trigger</th>
                    <th style={{ padding: "var(--space-2)" }}>Actions</th>
                    <th style={{ padding: "var(--space-2)" }}>Last run</th>
                    <th style={{ padding: "var(--space-2)" }}>Status</th>
                    <th style={{ padding: "var(--space-2)" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => {
                    const lastRun = lastRunByRule.get(rule.id);
                    return (
                      <tr
                        key={rule.id}
                        onClick={() => {
                          setCreating(false);
                          setSelectedRuleId(rule.id);
                        }}
                        style={{
                          borderBottom: "1px solid var(--border)",
                          cursor: "pointer",
                          background: rule.id === selectedRuleId ? "var(--surface)" : undefined,
                        }}
                      >
                        <td style={{ padding: "var(--space-2)" }}>{rule.name}</td>
                        <td style={{ padding: "var(--space-2)" }}>
                          <Badge label={TRIGGER_LABELS[rule.trigger_type] ?? rule.trigger_type} />
                        </td>
                        <td style={{ padding: "var(--space-2)" }}>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {rule.actions.map((action, i) => (
                              <Badge key={i} label={ACTION_LABELS[action.type] ?? action.type} />
                            ))}
                          </div>
                        </td>
                        <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: 13 }}>
                          {lastRun ? new Date(lastRun.executed_at).toLocaleDateString() : "—"}
                        </td>
                        <td style={{ padding: "var(--space-2)" }}>
                          <Badge
                            label={rule.status.replace("_", " ")}
                            tone={STATUS_TONE[rule.status]}
                          />
                        </td>
                        <td
                          style={{ padding: "var(--space-2)", textAlign: "right" }}
                          onClick={(event) => event.stopPropagation()}
                        >
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
                          {isAdmin && (rule.status === "active" || rule.status === "draft") && (
                            <Button
                              variant="text"
                              disabled={busyId === rule.id}
                              onClick={() =>
                                void decide(rule, rule.status === "active" ? "disabled" : "active")
                              }
                            >
                              {rule.status === "active" ? "Disable" : "Activate"}
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
                    );
                  })}
                </tbody>
              </table>
              </div>
            )}

            {recentRuns.length > 0 && (
              <div
                style={{
                  marginTop: 14,
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  padding: 10,
                }}
              >
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                  Recent runs
                </span>
                <div style={{ display: "flex", gap: 4, marginTop: 10, alignItems: "flex-end", height: 44 }}>
                  {recentRuns
                    .slice(0, 10)
                    .reverse()
                    .map((run) => (
                      <div
                        key={run.id}
                        title={`${run.rule_name} — ${run.status}`}
                        style={{
                          flex: 1,
                          background:
                            run.status === "failed" ? "var(--danger)" : "var(--accent)",
                          opacity: run.status === "success" ? 1 : 0.6,
                          height: RUN_STATUS_HEIGHT[run.status] ?? "50%",
                        }}
                      />
                    ))}
                </div>
              </div>
            )}
          </Card>
        </div>

        {(selectedRule || creating) &&
          (creating ? (
            <WorkflowRuleBuilder
              key="new"
              mode="create"
              onSaved={() => {
                closeBuilder();
                load();
              }}
              onCancel={closeBuilder}
            />
          ) : (
            <WorkflowRuleBuilder
              key={selectedRule!.id}
              mode={isAdmin ? "edit" : "view"}
              rule={selectedRule}
              onSaved={() => {
                closeBuilder();
                load();
              }}
              onCancel={closeBuilder}
            />
          ))}
      </div>

      {showHistory && (
        <WorkflowRunHistoryPanel rules={rules ?? []} onClose={() => setShowHistory(false)} />
      )}
    </div>
  );
}
