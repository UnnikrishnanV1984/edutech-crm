import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { listContacts, updateContact, type Contact } from "../api/contacts";
import { createFollowUpFlag } from "../api/followUpFlags";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { createTask } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { OwnerFilter } from "../components/OwnerFilter";
import { Skeleton } from "../components/Skeleton";
import { leadSourceColor, leadSourceLabel } from "../leadSource";
import { defaultOwnerFilterValue } from "../ownerFilter";
import { relativeTime } from "../relativeTime";
import { stageColor, stageIcon } from "../stageColor";
import { userDisplayName, useUsers } from "../useUsers";
import { useMe } from "../useMe";
import { CreateContactPanel } from "./CreateContactPanel";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const LEAD_SOURCE_OPTIONS = [
  { value: "meta", label: "Meta" },
  { value: "google", label: "Google" },
  { value: "web", label: "Web" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "manual", label: "Manual" },
];

const SORT_OPTIONS = [
  { value: "-updated_at", label: "Updated" },
  { value: "-created_at", label: "Created" },
  { value: "full_name", label: "Name" },
];

// Same convention as StaffDashboard.tsx's "my queue" SLA pills — color
// plus a text label always, never color alone (a stage's own color is
// tenant-configurable, so SLA urgency needs its own fixed vocabulary).
const SLA_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  breached: { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" },
  at_risk: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  on_track: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
};

function slaLabel(state: Contact["sla_state"]): string {
  if (state === null) return "—";
  return state.replace("_", " ");
}

// Filter-rail / bulk-toolbar chip — a clickable pill, distinct from the
// read-only Badge component. "selected" is a stronger neutral outline,
// not an accent fill — accent stays reserved for the "N selected" count
// and breach-adjacent emphasis, per the Classical design system's
// stroke-only accent rule.
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
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </button>
  );
}

function FilterSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
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
      <div style={{ marginTop: "var(--space-2)" }}>{children}</div>
    </div>
  );
}

export function ContactsListPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const navigate = useNavigate();

  const [contacts, setContacts] = useState<Contact[] | undefined>(undefined);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [leadSource, setLeadSource] = useState("");
  const [stageId, setStageId] = useState("");
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [sort, setSort] = useState("-updated_at");
  const [ownerId, setOwnerId] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [stages, setStages] = useState<PipelineStage[]>([]);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] = useState<"assign" | "task" | "flag" | null>(null);
  const [bulkOwnerId, setBulkOwnerId] = useState("");
  const [bulkTaskTitle, setBulkTaskTitle] = useState("");
  const [bulkTaskDue, setBulkTaskDue] = useState("");
  const [bulkFlagNote, setBulkFlagNote] = useState("");
  const [bulkFlagRemindOn, setBulkFlagRemindOn] = useState("");
  const [bulkError, setBulkError] = useState<string | undefined>(undefined);
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    if (me) setOwnerId(defaultOwnerFilterValue(me.user.role, me.user.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user.id, me?.user.role]);

  useEffect(() => {
    if (!token) return;
    listPipelineStages(token).then((response) => setStages(response.data));
  }, [token]);

  function load() {
    if (!token) {
      return;
    }
    setError(undefined);
    listContacts(token, {
      search: search || undefined,
      lead_source: leadSource || undefined,
      owner_id: me?.user.role === "counselor" ? undefined : ownerId,
      stage_id: stageId || undefined,
      has_follow_up_flag: flaggedOnly || undefined,
      sort,
      page,
      page_size: pageSize,
    })
      .then((response) => {
        setContacts(response.data);
        setTotal(response.meta.total);
        setSelectedIds(new Set());
      })
      .catch(() => setError("Couldn't load contacts"));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [
    token,
    search,
    leadSource,
    stageId,
    flaggedOnly,
    sort,
    ownerId,
    me,
    page,
    pageSize,
  ]);

  function updateFilter(update: () => void) {
    update();
    setPage(1);
  }

  const isDefaultOwnerFilter = me
    ? ownerId === defaultOwnerFilterValue(me.user.role, me.user.id)
    : true;
  const hasFilters = Boolean(
    search || leadSource || stageId || flaggedOnly || !isDefaultOwnerFilter,
  );
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageWindowStart = Math.max(1, Math.min(page - 2, totalPages - 4));
  const pageNumbers = Array.from(
    { length: Math.min(totalPages, 5) },
    (_, i) => pageWindowStart + i,
  );

  const canReassignOwner = me?.user.role === "manager" || me?.user.role === "admin";
  const canFlagFollowUp = me?.user.role === "manager" || me?.user.role === "admin";

  function toggleRow(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllOnPage() {
    if (!contacts) return;
    setSelectedIds((prev) => {
      const allSelected = contacts.every((c) => prev.has(c.id));
      return allSelected ? new Set() : new Set(contacts.map((c) => c.id));
    });
  }

  function closeBulk() {
    setBulkAction(null);
    setBulkOwnerId("");
    setBulkTaskTitle("");
    setBulkTaskDue("");
    setBulkFlagNote("");
    setBulkFlagRemindOn("");
    setBulkError(undefined);
  }

  async function runBulk(ids: string[], action: (id: string) => Promise<unknown>) {
    setBulkBusy(true);
    setBulkError(undefined);
    const failures: string[] = [];
    for (const id of ids) {
      try {
        await action(id);
      } catch {
        failures.push(id);
      }
    }
    setBulkBusy(false);
    if (failures.length > 0) {
      setBulkError(`${failures.length} of ${ids.length} contacts couldn't be updated.`);
      return;
    }
    closeBulk();
    load();
  }

  function applyBulkAssign() {
    if (!token || !bulkOwnerId) return;
    void runBulk(Array.from(selectedIds), (id) =>
      updateContact(token, id, { owner_id: bulkOwnerId }),
    );
  }

  function applyBulkTask() {
    if (!token || !bulkTaskTitle.trim()) return;
    void runBulk(Array.from(selectedIds), (id) =>
      createTask(token, {
        contact_id: id,
        title: bulkTaskTitle.trim(),
        due_at: bulkTaskDue ? new Date(bulkTaskDue).toISOString() : undefined,
      }),
    );
  }

  function applyBulkFlag() {
    if (!token || !bulkFlagNote.trim() || !bulkFlagRemindOn) return;
    void runBulk(Array.from(selectedIds), (id) =>
      createFollowUpFlag(token, {
        contact_id: id,
        note: bulkFlagNote.trim(),
        remind_on: bulkFlagRemindOn,
      }),
    );
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-4)",
          padding: "var(--space-4) var(--space-6)",
          borderBottom: "1px solid var(--border)",
          flexWrap: "wrap",
        }}
      >
        <h1 style={{ margin: 0 }}>Contacts</h1>
        <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", fontStyle: "italic" }}>
          {total.toLocaleString()} record{total === 1 ? "" : "s"}
        </span>
        <div style={{ flex: 1 }} />
        <input
          placeholder="Search name, email, phone"
          value={search}
          onChange={(event) => updateFilter(() => setSearch(event.target.value))}
          style={{ width: 240 }}
        />
        <Button variant="secondary" disabled title="CSV import isn't available yet">
          Import
        </Button>
        <Button variant="primary" onClick={() => setShowCreatePanel(true)}>
          + New contact
        </Button>
      </div>

      <div style={{ display: "flex", minWidth: 0 }}>
        <div
          style={{
            width: 196,
            flex: "none",
            borderRight: "1px solid var(--border)",
            padding: "var(--space-4) var(--space-3)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4)",
          }}
        >
          {me && me.user.role !== "counselor" && (
            <FilterSection label="Owner">
              <OwnerFilter
                role={me.user.role}
                meId={me.user.id}
                users={users}
                selectedUserId={ownerId}
                onChange={(value) => updateFilter(() => setOwnerId(value))}
              />
            </FilterSection>
          )}

          <FilterSection label="Lead source">
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {LEAD_SOURCE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 7,
                    fontSize: "var(--text-sm)",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={leadSource === option.value}
                    onChange={() =>
                      updateFilter(() =>
                        setLeadSource((prev) => (prev === option.value ? "" : option.value)),
                      )
                    }
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </FilterSection>

          <FilterSection label="Stage">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {stages.map((stage) => (
                <Chip
                  key={stage.id}
                  label={stage.name}
                  selected={stageId === stage.id}
                  onClick={() =>
                    updateFilter(() => setStageId((prev) => (prev === stage.id ? "" : stage.id)))
                  }
                />
              ))}
            </div>
          </FilterSection>

          <FilterSection label="Follow-up flag">
            <div style={{ display: "flex", gap: 6 }}>
              <Chip label="Any" selected={!flaggedOnly} onClick={() => updateFilter(() => setFlaggedOnly(false))} />
              <Chip
                label="Flagged"
                selected={flaggedOnly}
                onClick={() => updateFilter(() => setFlaggedOnly(true))}
              />
            </div>
          </FilterSection>

          <div style={{ height: 1, background: "var(--border)" }} />
          <span
            style={{
              fontSize: 10,
              fontWeight: "var(--weight-semibold)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--text-muted)",
            }}
          >
            Save this view
          </span>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              padding: "var(--space-3) var(--space-5)",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              flexWrap: "wrap",
            }}
          >
            {selectedIds.size > 0 && !bulkAction && (
              <>
                <Badge
                  variant="chip"
                  label={`${selectedIds.size} selected`}
                  tone={{ bg: "var(--accent-subtle)", fg: "var(--accent-hover)", border: "var(--accent)" }}
                />
                {canReassignOwner && (
                  <Chip label="Assign owner" onClick={() => setBulkAction("assign")} />
                )}
                <Chip label="Add task" onClick={() => setBulkAction("task")} />
                {canFlagFollowUp && (
                  <Chip label="Flag follow-up" onClick={() => setBulkAction("flag")} />
                )}
              </>
            )}

            {bulkAction === "assign" && (
              <>
                <select value={bulkOwnerId} onChange={(event) => setBulkOwnerId(event.target.value)}>
                  <option value="">Assign to…</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {userDisplayName(users, user.id)}
                    </option>
                  ))}
                </select>
                <Button variant="primary" disabled={!bulkOwnerId || bulkBusy} onClick={applyBulkAssign}>
                  Apply
                </Button>
                <Button variant="secondary" onClick={closeBulk}>
                  Cancel
                </Button>
              </>
            )}

            {bulkAction === "task" && (
              <>
                <input
                  placeholder="Task title"
                  value={bulkTaskTitle}
                  onChange={(event) => setBulkTaskTitle(event.target.value)}
                  style={{ width: 180 }}
                />
                <input
                  type="datetime-local"
                  value={bulkTaskDue}
                  onChange={(event) => setBulkTaskDue(event.target.value)}
                />
                <Button
                  variant="primary"
                  disabled={!bulkTaskTitle.trim() || bulkBusy}
                  onClick={applyBulkTask}
                >
                  Apply
                </Button>
                <Button variant="secondary" onClick={closeBulk}>
                  Cancel
                </Button>
              </>
            )}

            {bulkAction === "flag" && (
              <>
                <input
                  placeholder="Reason"
                  value={bulkFlagNote}
                  onChange={(event) => setBulkFlagNote(event.target.value)}
                  style={{ width: 160 }}
                />
                <input
                  type="date"
                  value={bulkFlagRemindOn}
                  onChange={(event) => setBulkFlagRemindOn(event.target.value)}
                />
                <Button
                  variant="primary"
                  disabled={!bulkFlagNote.trim() || !bulkFlagRemindOn || bulkBusy}
                  onClick={applyBulkFlag}
                >
                  Apply
                </Button>
                <Button variant="secondary" onClick={closeBulk}>
                  Cancel
                </Button>
              </>
            )}

            <div style={{ flex: 1 }} />
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
              Sort:
              <select value={sort} onChange={(event) => updateFilter(() => setSort(event.target.value))}>
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {bulkError && (
            <p role="alert" style={{ color: "var(--danger)", padding: "0 var(--space-5)", margin: "var(--space-2) 0 0" }}>
              {bulkError}
            </p>
          )}

          <div style={{ padding: "0 var(--space-5)" }}>
            {error && (
              <div style={{ margin: "var(--space-4) 0" }}>
                <p role="alert" style={{ color: "var(--danger)" }}>
                  {error}
                </p>
                <Button onClick={load}>Retry</Button>
              </div>
            )}

            {!error && contacts === undefined && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: "var(--space-4)" }}>
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} height={32} />
                ))}
              </div>
            )}

            {!error && contacts && contacts.length === 0 && !hasFilters && (
              <div style={{ marginTop: "var(--space-4)" }}>
                <EmptyState
                  headline="No leads yet"
                  subtext="Create your first contact to get started."
                  action={
                    <Button variant="primary" onClick={() => setShowCreatePanel(true)}>
                      New Contact
                    </Button>
                  }
                />
              </div>
            )}

            {!error && contacts && contacts.length === 0 && hasFilters && (
              <div style={{ marginTop: "var(--space-4)" }}>
                <EmptyState
                  headline="No contacts match your filters"
                  action={
                    <Button
                      onClick={() =>
                        updateFilter(() => {
                          setSearch("");
                          setLeadSource("");
                          setStageId("");
                          setFlaggedOnly(false);
                          setOwnerId(me ? defaultOwnerFilterValue(me.user.role, me.user.id) : undefined);
                        })
                      }
                    >
                      Clear filters
                    </Button>
                  }
                />
              </div>
            )}

            {!error && contacts && contacts.length > 0 && (
              <>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 13 }}>
                      <th style={{ padding: 8, width: 34 }}>
                        <input
                          type="checkbox"
                          checked={contacts.every((c) => selectedIds.has(c.id))}
                          onChange={toggleAllOnPage}
                          aria-label="Select all on this page"
                        />
                      </th>
                      <th style={{ padding: 8 }}>Name</th>
                      <th style={{ padding: 8 }}>Lead source</th>
                      <th style={{ padding: 8 }}>Stage</th>
                      <th style={{ padding: 8 }}>Owner</th>
                      <th style={{ padding: 8 }}>SLA</th>
                      <th style={{ padding: 8 }}>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contacts.map((contact) => {
                      const selected = selectedIds.has(contact.id);
                      return (
                        <tr
                          key={contact.id}
                          style={{
                            borderTop: "1px solid var(--border)",
                            background: selected ? "var(--surface)" : "transparent",
                          }}
                        >
                          <td style={{ padding: 8 }}>
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => toggleRow(contact.id)}
                              aria-label={`Select ${contact.full_name}`}
                            />
                          </td>
                          <td
                            style={{ padding: 8, cursor: "pointer" }}
                            onClick={() => navigate(`/contacts/${contact.id}`)}
                          >
                            {contact.full_name}
                          </td>
                          <td style={{ padding: 8 }}>
                            <Badge
                              label={leadSourceLabel(contact.lead_source)}
                              tone={leadSourceColor(contact.lead_source)}
                            />
                          </td>
                          <td style={{ padding: 8 }}>
                            {contact.stage_name ? (
                              (() => {
                                const index = stages.findIndex((s) => s.id === contact.stage_id);
                                const stage = stages[index];
                                return (
                                  <Badge
                                    label={contact.stage_name}
                                    icon={stage ? stageIcon(stage) : undefined}
                                    tone={stage ? stageColor(stage, Math.max(index, 0)) : undefined}
                                  />
                                );
                              })()
                            ) : (
                              <span style={{ color: "var(--text-muted)" }}>—</span>
                            )}
                          </td>
                          <td style={{ padding: 8 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <Avatar name={userDisplayName(users, contact.owner_id)} size={20} />
                              {userDisplayName(users, contact.owner_id)}
                            </div>
                          </td>
                          <td style={{ padding: 8 }}>
                            <Badge
                              label={slaLabel(contact.sla_state)}
                              tone={contact.sla_state ? SLA_TONE[contact.sla_state] : undefined}
                            />
                          </td>
                          <td style={{ padding: 8, color: "var(--text-muted)" }}>
                            {relativeTime(contact.updated_at)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                <div
                  style={{
                    padding: "var(--space-4) 0",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <Chip label="Prev" onClick={() => setPage((p) => Math.max(1, p - 1))} />
                  {pageNumbers.map((n) => (
                    <Chip key={n} label={String(n)} selected={n === page} onClick={() => setPage(n)} />
                  ))}
                  <Chip label="Next" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} />
                  <div style={{ flex: 1 }} />
                  <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                    <select
                      value={pageSize}
                      onChange={(event) => updateFilter(() => setPageSize(Number(event.target.value)))}
                    >
                      {PAGE_SIZE_OPTIONS.map((size) => (
                        <option key={size} value={size}>
                          {size} per page
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {showCreatePanel && (
        <CreateContactPanel
          onClose={() => setShowCreatePanel(false)}
          onCreated={(contact) => navigate(`/contacts/${contact.id}`)}
        />
      )}
    </div>
  );
}
