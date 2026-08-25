import { useEffect, useState } from "react";

import { listTasks, updateTask, type Task } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Spinner } from "../components/Spinner";
import { CreateTaskPanel } from "./CreateTaskPanel";

interface TasksSectionProps {
  contactId: string;
  contactName: string;
}

export function TasksSection({ contactId, contactName }: TasksSectionProps) {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<Task[] | undefined>(undefined);
  const [showDone, setShowDone] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  function load() {
    if (!token) return;
    listTasks(token, { contact_id: contactId }).then((response) => setTasks(response.data));
  }

  useEffect(load, [token, contactId]);

  async function toggleDone(task: Task) {
    if (!token) return;
    const nextStatus = task.status === "open" ? "done" : "open";
    setTasks((current) =>
      current?.map((t) => (t.id === task.id ? { ...t, status: nextStatus } : t)),
    );
    try {
      await updateTask(token, task.id, { status: nextStatus });
    } catch {
      load();
    }
  }

  const openTasks = tasks?.filter((t) => t.status === "open") ?? [];
  const doneTasks = tasks?.filter((t) => t.status === "done") ?? [];
  // Reading the clock for a display-only overdue flag, not for
  // reconciliation identity — safe to call during render here.
  // oxlint-disable-next-line react/purity
  const now = Date.now();

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
          Tasks
        </span>
        {tasks && <Badge label={String(openTasks.length).padStart(2, "0")} />}
        <div style={{ flex: 1 }} />
        <Button variant="secondary" onClick={() => setShowCreate(true)}>
          + Add
        </Button>
      </div>
      {tasks === undefined && (
        <div style={{ padding: 8, marginTop: "var(--space-3)" }}>
          <Spinner size={16} />
        </div>
      )}
      {tasks && openTasks.length === 0 && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <EmptyState headline="No open tasks" />
        </div>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: "var(--space-3) 0 0" }}>
        {openTasks.map((task) => {
          const overdue = task.due_at ? new Date(task.due_at).getTime() < now : false;
          return (
            <li
              key={task.id}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: 8 }}
            >
              <input
                type="checkbox"
                checked={false}
                onChange={() => void toggleDone(task)}
                aria-label={`Complete ${task.title}`}
              />
              <span>{task.title}</span>
              {task.due_at && (
                <span style={{ color: overdue ? "var(--danger)" : "var(--text-muted)", fontSize: 12 }}>
                  {new Date(task.due_at).toLocaleDateString()}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {doneTasks.length > 0 && (
        <>
          <Button variant="text" onClick={() => setShowDone((v) => !v)}>
            {showDone ? "Hide" : "Show"} {doneTasks.length} completed
          </Button>
          {showDone && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {doneTasks.map((task) => (
                <li
                  key={task.id}
                  style={{
                    padding: 8,
                    textDecoration: "line-through",
                    color: "var(--text-muted)",
                  }}
                >
                  {task.title}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {showCreate && (
        <CreateTaskPanel
          contactId={contactId}
          contactName={contactName}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </Card>
  );
}
