import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import type { PipelineStage } from "../api/pipelineStages";
import { REPORT_PERIOD_OPTIONS, type FunnelRow, type ReportPeriod } from "../api/reports";
import { listTasks, updateTask, type Task } from "../api/tasks";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Select } from "../components/Select";
import { Spinner } from "../components/Spinner";

// Shared widgets for the role dashboards, matching
// design_handoff_crm_wireframes/ screen 1a's "Pipeline by stage" and
// "My queue today" boxes — both Manager and Staff dashboards render the
// same two widgets (the wireframe's own note: the two role variants
// "differ only in whether the Team SLA block renders").

const ACCENT_TINT = { bg: "var(--accent-subtle)", fg: "var(--accent-hover)", border: "var(--accent)" };

export function MetricCard({
  label,
  value,
  accent,
  bar,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
  /** 1-4 picks one of the --kpi-N top-bar hues (index.css); omitted keeps a plain border. */
  bar?: 1 | 2 | 3 | 4;
}) {
  return (
    <div
      style={{
        flex: 1,
        border: "1px solid var(--border)",
        borderTop: bar ? `4px solid var(--kpi-${bar})` : "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        background: "var(--elevation-2)",
        boxShadow: "var(--shadow-sm)",
        padding: bar ? "calc(var(--space-4) - 3px) var(--space-4) var(--space-4)" : "var(--space-4)",
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: "var(--weight-semibold)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--text-muted)",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "var(--text-2xl)",
          lineHeight: "var(--line-2xl)",
          fontWeight: 800,
          letterSpacing: "-0.02em",
          fontVariantNumeric: "tabular-nums",
          color: accent ? "var(--accent)" : "var(--text-h)",
          marginTop: "var(--space-2)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function ToggleChip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        fontSize: "var(--text-xs)",
        padding: "3px 9px",
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

export function PipelineByStageCard({
  funnel,
  stages,
}: {
  funnel: FunnelRow[];
  stages: PipelineStage[];
}) {
  const [metric, setMetric] = useState<"count" | "value">("count");
  const maxCount = Math.max(1, ...funnel.map((f) => f.count));
  const maxValue = Math.max(1, ...funnel.map((f) => Number(f.value)));

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
          Pipeline by stage
        </span>
        <div style={{ flex: 1 }} />
        <ToggleChip label="Deals" selected={metric === "count"} onClick={() => setMetric("count")} />
        <ToggleChip label="Value" selected={metric === "value"} onClick={() => setMetric("value")} />
      </div>

      {funnel.length === 0 ? (
        <div style={{ marginTop: "var(--space-4)" }}>
          <EmptyState headline="No deals yet" />
        </div>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 150, marginTop: "var(--space-4)" }}>
            {funnel.map((row) => {
              const stage = stages.find((s) => s.id === row.stage_id);
              const pct =
                metric === "count" ? (row.count / maxCount) * 100 : (Number(row.value) / maxValue) * 100;
              return (
                <div
                  key={row.stage_id}
                  style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    height: "100%",
                  }}
                >
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: 4 }}>
                    {metric === "count" ? row.count : Number(row.value).toLocaleString()}
                  </span>
                  <div
                    style={{
                      width: "100%",
                      height: `${Math.max(pct, 3)}%`,
                      background: stage?.is_won ? "var(--accent)" : "var(--surface-hover)",
                      borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
                    }}
                  />
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: "var(--space-2)" }}>
            {funnel.map((row) => (
              <span
                key={row.stage_id}
                title={row.stage_name}
                style={{
                  flex: 1,
                  fontSize: 10,
                  color: "var(--text-muted)",
                  textAlign: "center",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {row.stage_name}
              </span>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

function dueBucket(dueAt: string | null): { label: string; accent?: boolean } {
  if (!dueAt) return { label: "No due date" };
  const due = new Date(dueAt).getTime();
  const now = new Date();
  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  const endOfToday = new Date(now);
  endOfToday.setHours(23, 59, 59, 999);
  if (due < startOfToday.getTime()) return { label: "Overdue", accent: true };
  if (due <= endOfToday.getTime()) return { label: "Today" };
  return { label: new Date(dueAt).toLocaleDateString(undefined, { weekday: "short" }) };
}

// A compact preview of the viewer's own open tasks, nearest-due-first —
// the full experience (grouping, undo-on-complete) lives on TasksPage;
// this widget completes a task immediately, no undo, since it's a
// dashboard preview rather than the task list itself.
export function MyQueueTodayCard({ token, meId }: { token: string; meId: string }) {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[] | undefined>(undefined);

  function load() {
    listTasks(token, { assignee_id: meId, status: "open", page_size: 100 }).then((response) => {
      const withDue = response.data.filter((t): t is Task & { due_at: string } => t.due_at !== null);
      withDue.sort((a, b) => new Date(a.due_at).getTime() - new Date(b.due_at).getTime());
      setTasks(withDue.slice(0, 5));
    });
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, meId]);

  async function complete(task: Task) {
    setTasks((current) => current?.filter((t) => t.id !== task.id));
    try {
      await updateTask(token, task.id, { status: "done" });
    } catch {
      load();
    }
  }

  return (
    <Card title="My queue today">
      {tasks === undefined ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-4)" }}>
          <Spinner size={18} />
        </div>
      ) : tasks.length === 0 ? (
        <EmptyState headline="You're all caught up" />
      ) : (
        <div>
          {tasks.map((task, index) => {
            const bucket = dueBucket(task.due_at);
            return (
              <div
                key={task.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "var(--space-2) 0",
                  borderTop: index === 0 ? "none" : "1px solid var(--border)",
                }}
              >
                <input
                  type="checkbox"
                  aria-label={`Complete ${task.title}`}
                  onChange={() => void complete(task)}
                />
                <div
                  style={{ flex: 1, cursor: task.contact_id ? "pointer" : undefined, minWidth: 0 }}
                  onClick={() => task.contact_id && navigate(`/contacts/${task.contact_id}`)}
                >
                  <div style={{ fontSize: "var(--text-sm)" }}>{task.title}</div>
                  {task.description && (
                    <div
                      style={{
                        fontSize: "var(--text-xs)",
                        color: "var(--text-muted)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {task.description}
                    </div>
                  )}
                </div>
                <Badge variant="chip" label={bucket.label} tone={bucket.accent ? ACCENT_TINT : undefined} />
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export function DashboardTopBar({
  roleLabel,
  period,
  onPeriodChange,
  children,
}: {
  roleLabel: string;
  period: ReportPeriod;
  onPeriodChange: (period: ReportPeriod) => void;
  children?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        marginBottom: "var(--space-5)",
        flexWrap: "wrap",
      }}
    >
      <h1 style={{ margin: 0 }}>Dashboard</h1>
      <span
        style={{
          fontSize: "var(--text-xs)",
          padding: "4px 10px",
          borderRadius: 999,
          border: "1px solid var(--text-h)",
          color: "var(--text-h)",
        }}
      >
        {roleLabel}
      </span>
      <div style={{ flex: 1 }} />
      <Select
        ariaLabel="Date range"
        value={period}
        onChange={(value) => onPeriodChange(value as ReportPeriod)}
        options={REPORT_PERIOD_OPTIONS}
        triggerStyle={{ width: 150 }}
      />
      {children}
    </div>
  );
}
