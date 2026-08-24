import { useEffect, useRef, useState } from "react";

import { listTasks, updateTask, type Task } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { OwnerFilter } from "../components/OwnerFilter";
import { useMe } from "../useMe";
import { useUsers } from "../useUsers";
import { CreateTaskPanel } from "./CreateTaskPanel";

type View = "list" | "board";

function groupTasks(tasks: Task[]) {
  const now = Date.now();
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const endOfToday = new Date();
  endOfToday.setHours(23, 59, 59, 999);

  const overdue: Task[] = [];
  const today: Task[] = [];
  const upcoming: Task[] = [];
  const noDueDate: Task[] = [];

  for (const task of tasks) {
    if (!task.due_at) {
      noDueDate.push(task);
      continue;
    }
    const due = new Date(task.due_at).getTime();
    if (due < now && due < startOfToday.getTime()) overdue.push(task);
    else if (due <= endOfToday.getTime()) today.push(task);
    else upcoming.push(task);
  }
  return { overdue, today, upcoming, noDueDate };
}

export function TasksPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const [view, setView] = useState<View>("list");
  // undefined = "my team" (manager) or "everyone" (admin) — omitted
  // from the request, RowScope decides what that means server-side.
  // A counselor's requests never set this (OwnerFilter renders nothing
  // for them, and their view is always "mine" regardless).
  const [assigneeId, setAssigneeId] = useState<string | undefined>(undefined);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [pendingUndo, setPendingUndo] = useState<Task | undefined>(undefined);
  const [showCreate, setShowCreate] = useState(false);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (me) setAssigneeId(me.user.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user.id]);

  function load() {
    if (!token) return;
    listTasks(token, {
      assignee_id: me?.user.role === "counselor" ? undefined : assigneeId,
      status: "open",
      page_size: 100,
    }).then((response) => setTasks(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, assigneeId, me]);

  async function complete(task: Task) {
    setTasks((current) => current.filter((t) => t.id !== task.id));
    setPendingUndo(task);
    try {
      await updateTask(token!, task.id, { status: "done" });
    } catch {
      setTasks((current) => [...current, task]);
      setPendingUndo(undefined);
      return;
    }
    undoTimer.current = setTimeout(() => setPendingUndo(undefined), 5000);
  }

  async function undo(task: Task) {
    if (undoTimer.current) clearTimeout(undoTimer.current);
    setPendingUndo(undefined);
    setTasks((current) => [task, ...current]);
    try {
      await updateTask(token!, task.id, { status: "open" });
    } catch {
      load();
    }
  }

  const groups = groupTasks(tasks);
  const now = Date.now();

  function TaskRow({ task }: { task: Task }) {
    const overdue = task.due_at ? new Date(task.due_at).getTime() < now : false;
    return (
      <li style={{ display: "flex", alignItems: "center", gap: 8, padding: 8 }}>
        <input
          type="checkbox"
          onChange={() => void complete(task)}
          aria-label={`Complete ${task.title}`}
        />
        <span>{task.title}</span>
        {task.due_at && (
          <span style={{ fontSize: 12, color: overdue ? "var(--danger)" : "var(--text-muted)" }}>
            {new Date(task.due_at).toLocaleString()}
          </span>
        )}
      </li>
    );
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h1>Tasks</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {me && (
            <OwnerFilter
              role={me.user.role}
              meId={me.user.id}
              users={users}
              selectedUserId={assigneeId}
              onChange={setAssigneeId}
            />
          )}
          <Button variant={view === "list" ? "primary" : "secondary"} onClick={() => setView("list")}>
            List
          </Button>
          <Button
            variant={view === "board" ? "primary" : "secondary"}
            onClick={() => setView("board")}
          >
            Board
          </Button>
          <Button variant="primary" onClick={() => setShowCreate(true)}>
            + New Task
          </Button>
        </div>
      </div>

      {pendingUndo && (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 8,
            marginBottom: 16,
            display: "flex",
            gap: 8,
            alignItems: "center",
          }}
        >
          <span>Completed "{pendingUndo.title}"</span>
          <Button variant="text" onClick={() => void undo(pendingUndo)}>
            Undo
          </Button>
        </div>
      )}

      {tasks.length === 0 && (
        <EmptyState
          headline={
            me?.user.role === "counselor" || assigneeId === me?.user.id
              ? "You're all caught up"
              : "No open tasks"
          }
        />
      )}

      {tasks.length > 0 && view === "list" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {groups.overdue.length > 0 && (
            <div>
              <h2 style={{ fontSize: 14, color: "var(--danger)" }}>Overdue</h2>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {groups.overdue.map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </ul>
            </div>
          )}
          {groups.today.length > 0 && (
            <div>
              <h2 style={{ fontSize: 14 }}>Today</h2>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {groups.today.map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </ul>
            </div>
          )}
          {(groups.upcoming.length > 0 || groups.noDueDate.length > 0) && (
            <div>
              <h2 style={{ fontSize: 14 }}>Upcoming</h2>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {[...groups.upcoming, ...groups.noDueDate].map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {tasks.length > 0 && view === "board" && (
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 14 }}>Open</h2>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {tasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </ul>
          </div>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 14 }}>Done</h2>
          </div>
        </div>
      )}

      {showCreate && (
        <CreateTaskPanel
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
