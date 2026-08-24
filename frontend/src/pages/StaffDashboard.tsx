import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getMyQueue, getMyStats, type MyQueueItem, type MyStats, type SlaUrgency } from "../api/reports";
import { listTasks, type Task } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useMe } from "../useMe";

const URGENCY_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  breached: { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" },
  at_risk: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  on_track: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
};

function urgencyLabel(state: SlaUrgency): string {
  if (state === null) return "no SLA yet";
  return state.replace("_", " ");
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div style={{ flex: 1 }}>
      <div
        style={{
          fontSize: "var(--text-2xl)",
          lineHeight: "var(--line-2xl)",
          fontWeight: "var(--weight-semibold)",
          color: "var(--text-h)",
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{label}</div>
    </div>
  );
}

export function StaffDashboard() {
  const { token } = useAuth();
  const { me } = useMe();
  const navigate = useNavigate();
  const [queue, setQueue] = useState<MyQueueItem[]>([]);
  const [stats, setStats] = useState<MyStats | undefined>(undefined);
  const [tasksToday, setTasksToday] = useState<Task[]>([]);

  useEffect(() => {
    if (!token || !me) return;
    getMyQueue(token).then((response) => setQueue(response.data));
    getMyStats(token).then((response) => setStats(response.data));
    listTasks(token, { assignee_id: me.user.id, status: "open", page_size: 100 }).then(
      (response) => {
        const endOfToday = new Date();
        endOfToday.setHours(23, 59, 59, 999);
        setTasksToday(
          response.data.filter((t) => t.due_at && new Date(t.due_at).getTime() <= endOfToday.getTime()),
        );
      },
    );
  }, [token, me]);

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <h1 style={{ marginBottom: "var(--space-5)" }}>My dashboard</h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {stats && (
          <Card>
            <div style={{ display: "flex", gap: "var(--space-6)" }}>
              <Stat value={stats.leads_worked} label="Leads worked" />
              <Stat value={`${Math.round(stats.conversion_rate * 100)}%`} label="Conversion rate" />
              <Stat value={tasksToday.length} label="Tasks due today" />
            </div>
          </Card>
        )}

        <Card title="My queue">
          {queue.length === 0 && <EmptyState headline="No assigned leads" />}
          {queue.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {queue.map((item, index) => (
                <li
                  key={item.deal_id}
                  onClick={() => navigate(`/contacts/${item.contact_id}`)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3) var(--space-2)",
                    borderTop: index === 0 ? "none" : "1px solid var(--border)",
                    cursor: "pointer",
                  }}
                >
                  <span>Deal {item.deal_id.slice(0, 8)}</span>
                  <Badge
                    variant="chip"
                    label={urgencyLabel(item.sla_state)}
                    tone={item.sla_state ? URGENCY_TONE[item.sla_state] : undefined}
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
