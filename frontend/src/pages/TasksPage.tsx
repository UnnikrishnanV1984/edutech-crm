import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getContact, type Contact } from "../api/contacts";
import { listTasks, updateTask, type Task } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { OwnerFilter } from "../components/OwnerFilter";
import { PageSpinner } from "../components/Spinner";
import { defaultOwnerFilterValue } from "../ownerFilter";
import { useMe } from "../useMe";
import { userDisplayName, useUsers } from "../useUsers";
import { CreateTaskPanel } from "./CreateTaskPanel";

type View = "list" | "board";

const ACCENT_TINT = { bg: "var(--accent-subtle)", fg: "var(--accent-hover)", border: "var(--accent)" };

function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function groupTasks(tasks: Task[]) {
  const now = Date.now();
  const startOfToday = startOfDay(new Date());
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

// "2 days late" / "Yesterday" for an overdue task, matching the
// wireframe's due-status chip; a plain date/time otherwise.
function dueLabel(task: Task, overdue: boolean): string {
  if (!task.due_at) return "No due date";
  const due = new Date(task.due_at);
  if (overdue) {
    const daysLate = Math.round(
      (startOfDay(new Date()).getTime() - startOfDay(due).getTime()) / 86_400_000,
    );
    if (daysLate <= 1) return "Yesterday";
    return `${daysLate} days late`;
  }
  return due.toLocaleString();
}

// Toggle chip — same pill pattern used on Contacts/Pipeline for
// Board/Table-style view switches.
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

function GroupHeader({
  label,
  count,
  accent,
}: {
  label: string;
  count: number;
  accent?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: "var(--weight-semibold)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: accent ? "var(--accent)" : "var(--text-muted)",
        }}
      >
        {label}
      </span>
      <Badge label={String(count).padStart(2, "0")} tone={accent ? ACCENT_TINT : undefined} />
      <div style={{ flex: 1, height: 2, background: accent ? "var(--accent)" : "var(--border)" }} />
    </div>
  );
}

export function TasksPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const navigate = useNavigate();
  const [view, setView] = useState<View>("list");
  // undefined = "my team" (manager) or "everyone" (admin) — omitted
  // from the request, RowScope decides what that means server-side.
  // A counselor's requests never set this (OwnerFilter renders nothing
  // for them, and their view is always "mine" regardless).
  const [assigneeId, setAssigneeId] = useState<string | undefined>(undefined);
  const [tasks, setTasks] = useState<Task[] | undefined>(undefined);
  const [contactsById, setContactsById] = useState<Record<string, Contact>>({});
  // Only fetched when the Board view is open — the List view has no use
  // for it, so this stays empty (and un-requested) otherwise.
  const [doneTasks, setDoneTasks] = useState<Task[]>([]);
  // Recently-completed tasks still shown inline (struck through, Undo
  // in place of the due date) for ~5s — design_handoff_crm_wireframes/
  // README's "Task complete: optimistic strikethrough + inline Undo".
  const [justCompleted, setJustCompleted] = useState<Record<string, Task>>({});
  const [showCreate, setShowCreate] = useState(false);
  const undoTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    if (me) setAssigneeId(defaultOwnerFilterValue(me.user.role, me.user.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user.id, me?.user.role]);

  function load() {
    if (!token) return;
    listTasks(token, {
      assignee_id: me?.user.role === "counselor" ? undefined : assigneeId,
      status: "open",
      page_size: 100,
    }).then((response) => {
      setTasks(response.data);
      const missing = [...new Set(response.data.map((t) => t.contact_id))].filter(
        (id) => !(id in contactsById),
      );
      Promise.all(missing.map((id) => getContact(token, id).catch(() => undefined))).then((results) => {
        setContactsById((current) => {
          const next = { ...current };
          for (const r of results) if (r) next[r.data.id] = r.data;
          return next;
        });
      });
    });
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, assigneeId, me]);

  function loadDone() {
    if (!token) return;
    listTasks(token, {
      assignee_id: me?.user.role === "counselor" ? undefined : assigneeId,
      status: "done",
      page_size: 100,
    }).then((response) => setDoneTasks(response.data));
  }

  useEffect(() => {
    if (view === "board") loadDone();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, token, assigneeId, me]);

  function clearJustCompleted(taskId: string) {
    const timer = undoTimers.current[taskId];
    if (timer) clearTimeout(timer);
    delete undoTimers.current[taskId];
    setJustCompleted((current) => {
      const next = { ...current };
      delete next[taskId];
      return next;
    });
  }

  async function complete(task: Task) {
    setTasks((current) => current?.filter((t) => t.id !== task.id));
    setJustCompleted((current) => ({ ...current, [task.id]: task }));
    try {
      await updateTask(token!, task.id, { status: "done" });
    } catch {
      setTasks((current) => [...(current ?? []), task]);
      clearJustCompleted(task.id);
      return;
    }
    undoTimers.current[task.id] = setTimeout(() => clearJustCompleted(task.id), 5000);
    if (view === "board") loadDone();
  }

  async function undo(task: Task) {
    clearJustCompleted(task.id);
    setTasks((current) => [task, ...(current ?? [])]);
    try {
      await updateTask(token!, task.id, { status: "open" });
    } catch {
      load();
    }
  }

  const displayTasks = [...(tasks ?? []), ...Object.values(justCompleted)];
  const groups = groupTasks(displayTasks);
  const openGroups = groupTasks(tasks ?? []);
  const hasNothingToShow =
    tasks !== undefined && tasks.length === 0 && Object.keys(justCompleted).length === 0;

  function TaskRow({ task, overdue }: { task: Task; overdue: boolean }) {
    const completed = task.id in justCompleted;
    const contact = contactsById[task.contact_id];
    return (
      <tr style={{ opacity: completed ? 0.5 : 1 }}>
        <td style={{ width: 30, padding: "var(--space-2)" }}>
          <input
            type="checkbox"
            checked={completed}
            disabled={completed}
            onChange={() => void complete(task)}
            aria-label={`Complete ${task.title}`}
          />
        </td>
        <td
          style={{
            padding: "var(--space-2)",
            textDecoration: completed ? "line-through" : undefined,
          }}
        >
          {task.title}
        </td>
        <td
          style={{
            padding: "var(--space-2)",
            color: "var(--text-muted)",
            fontSize: "var(--text-sm)",
          }}
        >
          {contact?.full_name ?? ""}
        </td>
        <td style={{ padding: "var(--space-2)" }}>
          {completed ? (
            <Chip label="Undo" onClick={() => void undo(task)} />
          ) : task.due_at ? (
            <Badge label={dueLabel(task, overdue)} tone={overdue ? ACCENT_TINT : undefined} />
          ) : null}
        </td>
        <td style={{ padding: "var(--space-2)", width: 28 }}>
          <Avatar name={userDisplayName(users, task.assignee_id)} size={20} />
        </td>
        <td style={{ padding: "var(--space-2)", textAlign: "right" }}>
          {!completed && (
            <Chip label="Open contact" onClick={() => navigate(`/contacts/${task.contact_id}`)} />
          )}
        </td>
      </tr>
    );
  }

  function TaskGroupTable({ rows, overdue }: { rows: Task[]; overdue: boolean }) {
    return (
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 6 }}>
        <tbody>
          {rows.map((task) => (
            <TaskRow key={task.id} task={task} overdue={overdue} />
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <h1 style={{ margin: 0 }}>Tasks</h1>
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
          <Chip label="List" selected={view === "list"} onClick={() => setView("list")} />
          <Chip label="Board" selected={view === "board"} onClick={() => setView("board")} />
          <Button variant="primary" onClick={() => setShowCreate(true)}>
            + New task
          </Button>
        </div>
      </div>

      {tasks === undefined && <PageSpinner />}

      {hasNothingToShow && (
        <EmptyState
          headline={
            me?.user.role === "counselor" || assigneeId === me?.user.id
              ? "You're all caught up"
              : "No open tasks"
          }
        />
      )}

      {!hasNothingToShow && tasks && view === "list" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {groups.overdue.length > 0 && (
            <div>
              <GroupHeader label="Overdue" count={openGroups.overdue.length} accent />
              <TaskGroupTable rows={groups.overdue} overdue />
            </div>
          )}
          {groups.today.length > 0 && (
            <div>
              <GroupHeader label="Today" count={openGroups.today.length} />
              <TaskGroupTable rows={groups.today} overdue={false} />
            </div>
          )}
          {(groups.upcoming.length > 0 || groups.noDueDate.length > 0) && (
            <div>
              <GroupHeader
                label="Upcoming"
                count={openGroups.upcoming.length + openGroups.noDueDate.length}
              />
              <TaskGroupTable rows={[...groups.upcoming, ...groups.noDueDate]} overdue={false} />
            </div>
          )}
        </div>
      )}

      {tasks && tasks.length > 0 && view === "board" && (
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <GroupHeader label="Open" count={tasks.length} />
            <TaskGroupTable
              rows={tasks}
              overdue={false}
            />
          </div>
          <div style={{ flex: 1 }}>
            <GroupHeader label="Done" count={doneTasks.length} />
            <ul style={{ listStyle: "none", padding: 0, marginTop: 6 }}>
              {doneTasks.map((task) => (
                <li
                  key={task.id}
                  style={{
                    padding: 8,
                    color: "var(--text-muted)",
                    textDecoration: "line-through",
                  }}
                >
                  {task.title}
                </li>
              ))}
            </ul>
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
