import { useEffect, useState } from "react";

import { listWorkflowRuns, type WorkflowRule, type WorkflowRun } from "../api/workflowRules";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { Select } from "../components/Select";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { PageSpinner } from "../components/Spinner";

const STATUS_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  success: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
  failed: { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" },
  retrying: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  skipped_unavailable: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
};

const PAGE_SIZE = 25;

interface WorkflowRunHistoryPanelProps {
  rules: WorkflowRule[];
  onClose: () => void;
}

export function WorkflowRunHistoryPanel({ rules, onClose }: WorkflowRunHistoryPanelProps) {
  const { token } = useAuth();
  const [ruleId, setRuleId] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [runs, setRuns] = useState<WorkflowRun[] | undefined>(undefined);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!token) return;
    // Re-show the spinner on every filter/page change, not just first
    // mount — same convention as the dashboards' period-driven effects.
    // oxlint-disable-next-line react/set-state-in-effect
    setRuns(undefined);
    listWorkflowRuns(token, { rule_id: ruleId, page, page_size: PAGE_SIZE }).then((response) => {
      setRuns(response.data);
      setTotal(response.meta.total);
    });
  }, [token, ruleId, page]);

  return (
    <SlideOverPanel title="Run history" onClose={onClose}>
      <label>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Rule</span>
        <div style={{ marginTop: 4 }}>
          <Select
            ariaLabel="Rule"
            value={ruleId ?? "all"}
            onChange={(value) => {
              setRuleId(value === "all" ? undefined : value);
              setPage(1);
            }}
            options={[
              { value: "all", label: "All rules" },
              ...rules.map((rule) => ({ value: rule.id, label: rule.name })),
            ]}
            triggerStyle={{ width: "100%" }}
          />
        </div>
      </label>

      {runs === undefined && <PageSpinner />}

      {runs && runs.length === 0 && <EmptyState headline="No runs yet" />}

      {runs && runs.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {runs.map((run) => (
            <div
              key={run.id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: "var(--space-2)",
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: "var(--weight-medium)" }}>{run.rule_name}</span>
                <Badge label={run.status.replace("_", " ")} tone={STATUS_TONE[run.status]} />
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                {run.trigger_source_type} · attempt {run.attempt} ·{" "}
                {new Date(run.executed_at).toLocaleString()}
              </div>
              {run.error_message && (
                <div style={{ fontSize: "var(--text-xs)", color: "var(--danger)" }}>
                  {run.error_message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {total > PAGE_SIZE && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Button variant="text" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            Page {page} of {Math.ceil(total / PAGE_SIZE)}
          </span>
          <Button
            variant="text"
            disabled={page >= Math.ceil(total / PAGE_SIZE)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </SlideOverPanel>
  );
}
