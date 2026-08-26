import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  listFollowUpFlags,
  resolveFollowUpFlag,
  snoozeFollowUpFlag,
  type FollowUpFlag,
} from "../api/followUpFlags";
import { useAuth } from "../auth/context";
import type { TenantUser } from "../api/users";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { defaultOwnerFilterValue } from "../ownerFilter";
import { useMe } from "../useMe";
import { userDisplayName, useUsers } from "../useUsers";
import { CreateFollowUpFlagPanel } from "./CreateFollowUpFlagPanel";

// Deliberately not the shared OwnerFilter component: that one's manager
// branch renders a Mine/My-team toggle (team = a manager's direct-report
// counselors), which doesn't fit here — follow-up flags are only ever
// owned by managers/admins, never counselors, and REQUIREMENTS.md §4.3
// (revised) makes this queue team-wide visibility for any Manager or
// Admin, not a self-vs-team split. Every viewer gets the same Mine +
// Everyone + full resource-list control.
function ResourceFilter({
  meId,
  users,
  selectedUserId,
  onChange,
}: {
  meId: string;
  users: TenantUser[];
  selectedUserId: string | undefined;
  onChange: (userId: string | undefined) => void;
}) {
  const isEveryone = selectedUserId === undefined;
  return (
    <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
      <Button
        variant={selectedUserId === meId ? "primary" : "secondary"}
        onClick={() => onChange(meId)}
      >
        Mine
      </Button>
      <select
        aria-label="Filter by owner"
        value={isEveryone ? "everyone" : selectedUserId}
        onChange={(event) => {
          const value = event.target.value;
          onChange(value === "everyone" ? undefined : value);
        }}
      >
        <option value="everyone">Everyone</option>
        {users.map((user) => (
          <option key={user.id} value={user.id}>
            {userDisplayName(users, user.id)}
          </option>
        ))}
      </select>
    </div>
  );
}

function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

// The wireframe's 4th column is literally labeled "Snoozed", but this
// schema has no history marker for "was this flag ever snoozed" (moving
// remind_on later reuses the one date field, same as the mockup's own
// annotation says — no schema change for this page, unlike Escalations'
// Phase 7e). So this bucket is really "everything due beyond this week" —
// which is also where a genuinely-snoozed flag naturally lands, just not
// exclusively so. Kept the mockup's label since the distinction is
// cosmetic, not a data-honesty issue: nothing here is fabricated.
function bucketFlags(flags: FollowUpFlag[]) {
  const today = startOfDay(new Date());
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 7);

  const overdue: FollowUpFlag[] = [];
  const dueToday: FollowUpFlag[] = [];
  const thisWeek: FollowUpFlag[] = [];
  const later: FollowUpFlag[] = [];

  for (const flag of flags) {
    const remindOn = startOfDay(new Date(flag.remind_on));
    if (remindOn < today) overdue.push(flag);
    else if (remindOn.getTime() === today.getTime()) dueToday.push(flag);
    else if (remindOn <= weekEnd) thisWeek.push(flag);
    else later.push(flag);
  }
  return { overdue, dueToday, thisWeek, later };
}

function Chip({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-medium)",
        padding: "3px 8px",
        borderRadius: 999,
        border: "1px solid var(--text-h)",
        background: "transparent",
        color: "var(--text-h)",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

function ColumnHeader({
  label,
  count,
  accent,
  muted,
}: {
  label: string;
  count: number;
  accent?: boolean;
  muted?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        paddingBottom: 8,
        borderBottom: `2px solid ${accent ? "var(--accent)" : "var(--border)"}`,
        opacity: muted ? 0.6 : 1,
      }}
    >
      <span
        style={{
          fontSize: "var(--text-xs)",
          fontWeight: "var(--weight-semibold)",
          color: accent ? "var(--accent)" : "var(--text-h)",
        }}
      >
        {label}
      </span>
      <div style={{ flex: 1 }} />
      <Badge
        label={String(count).padStart(2, "0")}
        tone={accent ? { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" } : undefined}
      />
    </div>
  );
}

interface FlagCardProps {
  flag: FollowUpFlag;
  showActions: boolean;
  snoozing: boolean;
  snoozeDate: string;
  busy: boolean;
  onStartSnooze: () => void;
  onCancelSnooze: () => void;
  onSnoozeDateChange: (value: string) => void;
  onConfirmSnooze: () => void;
  onDone: () => void;
}

function FlagCard({
  flag,
  showActions,
  snoozing,
  snoozeDate,
  busy,
  onStartSnooze,
  onCancelSnooze,
  onSnoozeDateChange,
  onConfirmSnooze,
  onDone,
}: FlagCardProps) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        padding: "var(--space-3)",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontWeight: "var(--weight-medium)" }}>{flag.contact_name ?? "Contact"}</div>
      <div
        style={{
          fontSize: "var(--text-sm)",
          color: "var(--text-muted)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {flag.note}
      </div>
      {showActions && !snoozing && (
        <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
          <Badge label="Reason" />
          <Chip label="Snooze" onClick={onStartSnooze} />
          <Chip label="Done" onClick={onDone} />
        </div>
      )}
      {snoozing && (
        <div style={{ display: "flex", gap: 6, marginTop: 4, alignItems: "center" }}>
          <input
            type="date"
            value={snoozeDate}
            onChange={(event) => onSnoozeDateChange(event.target.value)}
            style={{ fontSize: "var(--text-xs)", padding: "2px 4px" }}
          />
          <Chip label={busy ? "Saving…" : "Confirm"} onClick={onConfirmSnooze} />
          <Button variant="text" onClick={onCancelSnooze}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}

export function FollowUpFlagsPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const navigate = useNavigate();
  const [managerId, setManagerId] = useState<string | undefined>(undefined);
  const [flags, setFlags] = useState<FollowUpFlag[] | undefined>(undefined);
  const [showCreate, setShowCreate] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);
  const [snoozingId, setSnoozingId] = useState<string | undefined>(undefined);
  const [snoozeDate, setSnoozeDate] = useState("");

  useEffect(() => {
    if (me) setManagerId(defaultOwnerFilterValue(me.user.role, me.user.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user.id, me?.user.role]);

  function load() {
    if (!token) return;
    listFollowUpFlags(token, { manager_id: managerId }).then((response) => setFlags(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, managerId]);

  if (me && me.user.role === "counselor") {
    return (
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
        <EmptyState headline="Managers and admins only" />
      </div>
    );
  }

  async function resolve(flag: FollowUpFlag) {
    if (!token) return;
    setBusyId(flag.id);
    try {
      await resolveFollowUpFlag(token, flag.id);
      setFlags((current) => current?.filter((f) => f.id !== flag.id));
    } finally {
      setBusyId(undefined);
    }
  }

  function startSnooze(flag: FollowUpFlag) {
    const suggested = new Date();
    suggested.setDate(suggested.getDate() + 7);
    setSnoozeDate(suggested.toISOString().slice(0, 10));
    setSnoozingId(flag.id);
  }

  async function confirmSnooze(flag: FollowUpFlag) {
    if (!token || !snoozeDate) return;
    setBusyId(flag.id);
    try {
      const response = await snoozeFollowUpFlag(token, flag.id, snoozeDate);
      setFlags((current) => current?.map((f) => (f.id === flag.id ? response.data : f)));
      setSnoozingId(undefined);
    } finally {
      setBusyId(undefined);
    }
  }

  const openFlags = flags?.filter((f) => !f.resolved_at) ?? [];
  const buckets = bucketFlags(openFlags);

  function renderCard(flag: FollowUpFlag, showActions: boolean) {
    return (
      <FlagCard
        key={flag.id}
        flag={flag}
        showActions={showActions}
        snoozing={snoozingId === flag.id}
        snoozeDate={snoozeDate}
        busy={busyId === flag.id}
        onStartSnooze={() => startSnooze(flag)}
        onCancelSnooze={() => setSnoozingId(undefined)}
        onSnoozeDateChange={setSnoozeDate}
        onConfirmSnooze={() => void confirmSnooze(flag)}
        onDone={() => void resolve(flag)}
      />
    );
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0 }}>Follow-ups</h1>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
            flags raised by rules or by hand
          </div>
        </div>
        <div style={{ flex: 1 }} />
        {me && (
          <ResourceFilter
            meId={me.user.id}
            users={users}
            selectedUserId={managerId}
            onChange={setManagerId}
          />
        )}
        <Button variant="primary" onClick={() => setShowCreate(true)}>
          + Flag a contact
        </Button>
      </div>

      {flags === undefined && <PageSpinner />}

      {flags && (
        <>
          <div className="grid-4col" style={{ alignItems: "start", marginBottom: "var(--space-5)" }}>
            <div>
              <ColumnHeader label="Overdue" count={buckets.overdue.length} accent />
              <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 11 }}>
                {buckets.overdue.map((flag) => renderCard(flag, true))}
              </div>
            </div>
            <div>
              <ColumnHeader label="Due today" count={buckets.dueToday.length} />
              <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 11 }}>
                {buckets.dueToday.map((flag) => renderCard(flag, true))}
              </div>
            </div>
            <div>
              <ColumnHeader label="This week" count={buckets.thisWeek.length} />
              <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 11 }}>
                {buckets.thisWeek.map((flag) => renderCard(flag, false))}
              </div>
            </div>
            <div>
              <ColumnHeader label="Snoozed" count={buckets.later.length} muted />
              <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 11, opacity: 0.6 }}>
                {buckets.later.map((flag) => renderCard(flag, false))}
              </div>
            </div>
          </div>

          {openFlags.length === 0 && (
            <EmptyState
              headline="No follow-ups scheduled"
              subtext="A personal reminder tool — separate from escalations, never notifies the counselor."
            />
          )}

          {openFlags.length > 0 && (
            <Card>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: "var(--weight-semibold)",
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "var(--text-muted)",
                  }}
                >
                  All flags
                </span>
              </div>
              <div className="table-scroll">
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                    <th style={{ padding: "var(--space-2)" }}>Contact</th>
                    <th style={{ padding: "var(--space-2)" }}>Reason</th>
                    <th style={{ padding: "var(--space-2)" }}>Raised by</th>
                    <th style={{ padding: "var(--space-2)" }}>Due</th>
                    <th style={{ padding: "var(--space-2)" }}>Status</th>
                    <th style={{ padding: "var(--space-2)" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {openFlags.map((flag) => {
                    const isOverdue = buckets.overdue.includes(flag);
                    const isDueToday = buckets.dueToday.includes(flag);
                    const statusLabel = isOverdue ? "Overdue" : isDueToday ? "Due today" : "Upcoming";
                    return (
                      <tr key={flag.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ padding: "var(--space-2)" }}>
                          {flag.resolved_contact_id ? (
                            <button
                              type="button"
                              onClick={() => navigate(`/contacts/${flag.resolved_contact_id}`)}
                              style={{
                                background: "none",
                                border: "none",
                                padding: 0,
                                color: "var(--text-h)",
                                textDecoration: "underline",
                                cursor: "pointer",
                              }}
                            >
                              {flag.contact_name ?? "View contact"}
                            </button>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td style={{ padding: "var(--space-2)" }}>
                          <Badge label={flag.note} />
                        </td>
                        <td style={{ padding: "var(--space-2)", color: "var(--text-muted)" }}>
                          {flag.manager_name ?? "—"}
                        </td>
                        <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: 13 }}>
                          {new Date(flag.remind_on).toLocaleDateString()}
                        </td>
                        <td style={{ padding: "var(--space-2)" }}>
                          <Badge
                            label={statusLabel}
                            tone={
                              isOverdue
                                ? { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" }
                                : undefined
                            }
                          />
                        </td>
                        <td style={{ padding: "var(--space-2)", textAlign: "right" }}>
                          <Chip label="Done" onClick={() => void resolve(flag)} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            </Card>
          )}
        </>
      )}

      {showCreate && (
        <CreateFollowUpFlagPanel
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
