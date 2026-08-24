import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getMyQueue, getMyStats, type MyQueueItem, type MyStats, type SlaUrgency } from "../api/reports";
import { listTasks, type Task } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
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
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <h1 style={{ marginBottom: 16 }}>My dashboard</h1>

      {stats && (
        <div style={{ display: "flex", gap: 24, marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 24, fontWeight: "var(--weight-semibold)" }}>
              {stats.leads_worked}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Leads worked</div>
          </div>
          <div>
            <div style={{ fontSize: 24, fontWeight: "var(--weight-semibold)" }}>
              {Math.round(stats.conversion_rate * 100)}%
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Conversion rate</div>
          </div>
          <div>
            <div style={{ fontSize: 24, fontWeight: "var(--weight-semibold)" }}>
              {tasksToday.length}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Tasks due today</div>
          </div>
        </div>
      )}

      <h2 style={{ fontSize: 16, marginBottom: 8 }}>My queue</h2>
      {queue.length === 0 && <EmptyState headline="No assigned leads" />}
      {queue.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {queue.map((item) => (
            <li
              key={item.deal_id}
              onClick={() => navigate(`/contacts/${item.contact_id}`)}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: 8,
                borderBottom: "1px solid var(--border)",
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
    </div>
  );
}
