import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listContacts, type Contact } from "../api/contacts";
import { listCourses, type Course } from "../api/courses";
import { listDeals, updateDeal, type Deal } from "../api/deals";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { OwnerFilter } from "../components/OwnerFilter";
import { Pager } from "../components/Pager";
import { PageSpinner } from "../components/Spinner";
import { useToast } from "../components/toastContext";
import { defaultOwnerFilterValue } from "../ownerFilter";
import { stageColor, stageIcon } from "../stageColor";
import type { TenantUser } from "../api/users";
import { userDisplayName, useUsers } from "../useUsers";
import { useIsMobile } from "../useIsMobile";
import { useMe } from "../useMe";
import { CreateDealPanel } from "./CreateDealPanel";

const LEAD_SOURCE_OPTIONS = [
  { value: "meta", label: "Meta" },
  { value: "google", label: "Google" },
  { value: "web", label: "Web" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "manual", label: "Manual" },
];

const SLA_STATE_OPTIONS = [
  { value: "on_track", label: "On track" },
  { value: "at_risk", label: "At risk" },
  { value: "breached", label: "Breached" },
];

// The Classical design system's one emphasis treatment (accent-tint
// fill) — used generically for "this needs attention": an SLA-at-risk
// card, the won-stage count, the "N selected" bulk-toolbar badge. Never
// a solid accent block, per the design system's stroke-only rule.
const ACCENT_TINT = { bg: "var(--accent-subtle)", fg: "var(--accent-hover)", border: "var(--accent)" };
const SLA_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  breached: ACCENT_TINT,
  at_risk: ACCENT_TINT,
};

// A pill-styled <select> — matches the wireframe's "Label ▾" filter
// chips while staying a real, accessible native control.
function FilterSelect({
  placeholder,
  value,
  onChange,
  options,
}: {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      style={{
        fontSize: "var(--text-xs)",
        padding: "4px 8px",
        borderRadius: 999,
        border: `1px solid ${value ? "var(--text-h)" : "var(--border)"}`,
        background: "transparent",
        color: value ? "var(--text-h)" : "var(--text-muted)",
      }}
    >
      <option value="">{placeholder} ▾</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

// Every card carries a "Move ▾" select alongside the drag interaction —
// design_handoff_crm_wireframes/ screen 13's phone mock replaces drag
// with this control entirely below 900px (native HTML5 drag doesn't fire
// on touch), and it's harmless/useful as a keyboard-accessible fallback
// on desktop too, so it's always rendered rather than conditionally
// swapped in.
function DealCard({
  deal,
  contact,
  stage,
  stages,
  stageIndex,
  users,
  courseName,
  dragging,
  onDragStart,
  onDragEnd,
  onClick,
  onMove,
}: {
  deal: Deal;
  contact: Contact | undefined;
  stage: PipelineStage;
  stages: PipelineStage[];
  stageIndex: number;
  users: TenantUser[];
  courseName: (courseId: string | null) => string | null;
  dragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
  onClick: () => void;
  onMove: (deal: Deal, stage: PipelineStage) => void;
}) {
  const tone = stageColor(stage, stageIndex);
  // Reading the clock for a display-only "days in stage" label, not for
  // reconciliation identity — safe to call during render here (same
  // reasoning as TasksSection.tsx's own now/Date.now() usage).
  // oxlint-disable-next-line react/purity
  const now = Date.now();
  const daysInStage = Math.floor((now - new Date(deal.stage_changed_at).getTime()) / 86_400_000);
  const atRisk = deal.sla_state === "at_risk" || deal.sla_state === "breached";

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onClick}
      style={{
        background: "var(--elevation-2)",
        borderLeft: `2px solid ${atRisk ? "var(--accent)" : tone.fg}`,
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "var(--space-2)",
        cursor: "grab",
        boxShadow: dragging ? "var(--shadow-lg)" : undefined,
        transform: dragging ? "rotate(-0.6deg)" : undefined,
        transition: "box-shadow 120ms ease, transform 120ms ease",
      }}
    >
      <div style={{ fontWeight: "var(--weight-semibold)", fontSize: "var(--text-sm)" }}>
        {contact?.full_name ?? "…"}
      </div>
      {courseName(deal.course_id) && (
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
          {courseName(deal.course_id)}
        </div>
      )}
      {Number(deal.value) > 0 && (
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
          {deal.currency} {Number(deal.value).toLocaleString()}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
        <Avatar name={userDisplayName(users, deal.owner_id)} size={18} />
        {stage.is_invoice_stage ? (
          <Badge variant="chip" label="Invoice" />
        ) : atRisk ? (
          <Badge variant="chip" label="SLA" tone={SLA_TONE[deal.sla_state ?? "at_risk"]} />
        ) : (
          <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            {daysInStage}d
          </span>
        )}
        <div style={{ flex: 1 }} />
        <select
          aria-label={`Move ${contact?.full_name ?? "deal"} to a different stage`}
          value=""
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => {
            const target = stages.find((s) => s.id === event.target.value);
            if (target) onMove(deal, target);
            event.currentTarget.value = "";
          }}
          style={{
            fontSize: "var(--text-xs)",
            padding: "2px 6px",
            borderRadius: 999,
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-muted)",
          }}
        >
          <option value="">Move ▾</option>
          {stages
            .filter((s) => s.id !== stage.id)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
        </select>
      </div>
    </div>
  );
}

export function PipelinePage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const isMobile = useIsMobile();

  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [mobileStageId, setMobileStageId] = useState<string | undefined>(undefined);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [contactsById, setContactsById] = useState<Record<string, Contact>>({});
  // undefined = "my team" (manager) or "everyone" (admin), per
  // ADMIN_UX_IMPROVEMENTS_PLAN.md Sec5 — same OwnerFilter contract as
  // TasksPage.tsx.
  const [ownerId, setOwnerId] = useState<string | undefined>(undefined);
  const [leadSource, setLeadSource] = useState("");
  const [courseFilter, setCourseFilter] = useState("");
  const [slaState, setSlaState] = useState("");
  const [view, setView] = useState<"board" | "table">("board");
  const [draggingDealId, setDraggingDealId] = useState<string | undefined>(undefined);
  const [dragOverStageId, setDragOverStageId] = useState<string | undefined>(undefined);
  const [confirmDrop, setConfirmDrop] = useState<{ deal: Deal; stage: PipelineStage } | undefined>(
    undefined,
  );
  const [showCreate, setShowCreate] = useState(false);
  const [loaded, setLoaded] = useState(false);
  // Table view's own pagination — client-side, over the same `deals`
  // array the Kanban board already loads in full (page_size: 100 below),
  // since a drag-and-drop board needs its full working set in memory
  // regardless. Keeps the flat table from rendering unboundedly long.
  const [tablePage, setTablePage] = useState(1);
  const [tablePageSize, setTablePageSize] = useState(25);

  function load() {
    if (!token) return;
    listPipelineStages(token).then((response) => setStages(response.data));
    listCourses(token).then((response) => setCourses(response.data));
    listDeals(token, {
      owner_id: me?.user.role === "counselor" ? undefined : ownerId,
      course_id: courseFilter || undefined,
      sla_state: slaState || undefined,
      page_size: 100,
    }).then(
      (response) => {
        setDeals(response.data);
        setLoaded(true);
        const missing = [...new Set(response.data.map((d) => d.contact_id))].filter(
          (id) => !(id in contactsById),
        );
        if (missing.length > 0) {
          listContacts(token, { ids: missing }).then((contactsResponse) => {
            setContactsById((current) => {
              const next = { ...current };
              for (const c of contactsResponse.data) next[c.id] = c;
              return next;
            });
          });
        }
      },
    );
  }

  useEffect(() => {
    if (me) setOwnerId(defaultOwnerFilterValue(me.user.role, me.user.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user.id, me?.user.role]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, ownerId, courseFilter, slaState, me]);

  useEffect(() => {
    if (stages.length > 0 && !stages.some((s) => s.id === mobileStageId)) {
      setMobileStageId(stages[0]!.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stages]);

  function courseName(courseId: string | null) {
    if (!courseId) return null; // non-EdTech deal, no course to show
    return courses.find((c) => c.id === courseId)?.name ?? "";
  }

  const visibleDeals = leadSource
    ? deals.filter((d) => contactsById[d.contact_id]?.lead_source === leadSource)
    : deals;

  useEffect(() => {
    setTablePage(1);
  }, [leadSource, courseFilter, slaState, ownerId, view]);

  const tableDeals = visibleDeals.slice(
    (tablePage - 1) * tablePageSize,
    tablePage * tablePageSize,
  );

  async function moveDeal(deal: Deal, stage: PipelineStage) {
    const previousStageId = deal.stage_id;
    setDeals((current) =>
      current.map((d) => (d.id === deal.id ? { ...d, stage_id: stage.id } : d)),
    );
    try {
      await updateDeal(token!, deal.id, { stage_id: stage.id });
    } catch {
      setDeals((current) =>
        current.map((d) => (d.id === deal.id ? { ...d, stage_id: previousStageId } : d)),
      );
      showToast({
        message: `Couldn't move ${contactsById[deal.contact_id]?.full_name ?? "contact"} to ${stage.name}`,
        actionLabel: "Retry",
        onAction: () => void moveDeal(deal, stage),
      });
    }
  }

  function handleDrop(stage: PipelineStage) {
    setDragOverStageId(undefined);
    if (!draggingDealId) return;
    const deal = deals.find((d) => d.id === draggingDealId);
    setDraggingDealId(undefined);
    if (!deal || deal.stage_id === stage.id) return;

    if (stage.is_won || stage.is_lost) {
      setConfirmDrop({ deal, stage });
      return;
    }
    void moveDeal(deal, stage);
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          padding: "var(--space-4) var(--space-6)",
          borderBottom: "1px solid var(--border)",
          flexWrap: "wrap",
        }}
      >
        <h1 style={{ margin: 0 }}>Pipelines</h1>
        <select disabled title="Multiple pipelines aren't supported yet" style={{ width: 160 }}>
          <option>Pipeline ▾</option>
        </select>
        <div style={{ flex: 1 }} />
        {me && (
          <OwnerFilter
            role={me.user.role}
            meId={me.user.id}
            users={users}
            selectedUserId={ownerId}
            onChange={setOwnerId}
          />
        )}
        <Button variant="primary" onClick={() => setShowCreate(true)}>
          + New deal
        </Button>
      </div>

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
        <span
          style={{
            fontSize: "var(--text-xs)",
            padding: "4px 10px",
            borderRadius: 999,
            border: "1px solid var(--text-h)",
            color: "var(--text-h)",
          }}
        >
          Filters
        </span>
        <FilterSelect
          placeholder="Lead source"
          value={leadSource}
          onChange={setLeadSource}
          options={LEAD_SOURCE_OPTIONS}
        />
        <FilterSelect
          placeholder="Course"
          value={courseFilter}
          onChange={setCourseFilter}
          options={courses.map((c) => ({ value: c.id, label: c.name }))}
        />
        <FilterSelect
          placeholder="SLA state"
          value={slaState}
          onChange={setSlaState}
          options={SLA_STATE_OPTIONS}
        />
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
          {view === "board" ? "Board" : "Table"}
        </span>
        <button
          type="button"
          onClick={() => setView((v) => (v === "board" ? "table" : "board"))}
          style={{
            fontSize: "var(--text-xs)",
            padding: "4px 10px",
            borderRadius: 999,
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-muted)",
            cursor: "pointer",
          }}
        >
          {view === "board" ? "Table" : "Board"}
        </button>
      </div>

      <div style={{ padding: "var(--space-4) var(--space-5)" }}>
        {!loaded && <PageSpinner />}

        {loaded && view === "board" && isMobile && (
          <>
            <div
              className="pipeline-columns"
              style={{ paddingBottom: "var(--space-2)", marginBottom: "var(--space-3)" }}
            >
              {stages.map((stage) => {
                const count = visibleDeals.filter((d) => d.stage_id === stage.id).length;
                const active = stage.id === mobileStageId;
                return (
                  <button
                    key={stage.id}
                    type="button"
                    onClick={() => setMobileStageId(stage.id)}
                    style={{
                      flexShrink: 0,
                      fontSize: "var(--text-xs)",
                      fontWeight: "var(--weight-semibold)",
                      padding: "var(--space-2) var(--space-3)",
                      borderRadius: 999,
                      border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                      background: active ? "var(--accent-subtle)" : "transparent",
                      color: active ? "var(--text-h)" : "var(--text-muted)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {stage.name} {String(count).padStart(2, "0")}
                  </button>
                );
              })}
            </div>

            {(() => {
              const stageIndex = stages.findIndex((s) => s.id === mobileStageId);
              const stage = stages[stageIndex];
              if (!stage) return null;
              const columnDeals = visibleDeals.filter((d) => d.stage_id === stage.id);
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  {columnDeals.length === 0 && (
                    <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
                      Nothing in {stage.name} yet.
                    </p>
                  )}
                  {columnDeals.map((deal) => (
                    <DealCard
                      key={deal.id}
                      deal={deal}
                      contact={contactsById[deal.contact_id]}
                      stage={stage}
                      stages={stages}
                      stageIndex={stageIndex}
                      users={users}
                      courseName={courseName}
                      dragging={false}
                      onDragStart={() => undefined}
                      onDragEnd={() => undefined}
                      onClick={() => navigate(`/contacts/${deal.contact_id}`)}
                      onMove={(d, s) => void moveDeal(d, s)}
                    />
                  ))}
                </div>
              );
            })()}
          </>
        )}

        {loaded && view === "board" && !isMobile && (
          <>
            <div className="pipeline-columns">
              {stages.map((stage, index) => {
                const columnDeals = visibleDeals.filter((d) => d.stage_id === stage.id);
                const isDragOver = dragOverStageId === stage.id;
                return (
                  <div
                    key={stage.id}
                    onDragOver={(event) => {
                      event.preventDefault();
                      if (draggingDealId) setDragOverStageId(stage.id);
                    }}
                    onDragLeave={() =>
                      setDragOverStageId((current) => (current === stage.id ? undefined : current))
                    }
                    onDrop={() => handleDrop(stage)}
                    style={{
                      width: 196,
                      flexShrink: 0,
                      background: "var(--surface)",
                      borderRadius: "var(--radius)",
                      border: "1px solid var(--border)",
                      opacity: stage.is_lost ? 0.55 : 1,
                    }}
                  >
                    <div
                      style={{
                        borderTop: `2px solid ${stage.is_won ? "var(--accent)" : "var(--border)"}`,
                        borderRadius: "var(--radius) var(--radius) 0 0",
                        padding: "var(--space-2)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: "var(--text-xs)",
                        fontWeight: "var(--weight-semibold)",
                      }}
                    >
                      <span>
                        {stage.name} {stageIcon(stage)}
                      </span>
                      <Badge
                        label={String(columnDeals.length).padStart(2, "0")}
                        tone={stage.is_won ? ACCENT_TINT : undefined}
                      />
                    </div>
                    <div
                      style={{
                        padding: "var(--space-2)",
                        display: "flex",
                        flexDirection: "column",
                        gap: "var(--space-2)",
                      }}
                    >
                      {columnDeals.map((deal) => (
                        <DealCard
                          key={deal.id}
                          deal={deal}
                          contact={contactsById[deal.contact_id]}
                          stage={stage}
                          stages={stages}
                          stageIndex={index}
                          users={users}
                          courseName={courseName}
                          dragging={draggingDealId === deal.id}
                          onDragStart={() => setDraggingDealId(deal.id)}
                          onDragEnd={() => {
                            setDraggingDealId(undefined);
                            setDragOverStageId(undefined);
                          }}
                          onClick={() => navigate(`/contacts/${deal.contact_id}`)}
                          onMove={(d, s) => void moveDeal(d, s)}
                        />
                      ))}
                      {isDragOver && (
                        <div
                          style={{
                            border: "1px dashed var(--border)",
                            borderRadius: "var(--radius)",
                            height: 48,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 9,
                            letterSpacing: "0.1em",
                            textTransform: "uppercase",
                            color: "var(--text-muted)",
                          }}
                        >
                          Drop target
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: "var(--space-3)" }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                Horizontal scroll →
              </span>
              <div style={{ flex: 1, height: 4, background: "var(--surface-hover)", borderRadius: 999 }}>
                <div style={{ width: "40%", height: 4, background: "var(--border)", borderRadius: 999 }} />
              </div>
            </div>
          </>
        )}

        {loaded && view === "table" && (
          <div className="table-scroll">
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 13 }}>
                <th style={{ padding: 8 }}>Name</th>
                <th style={{ padding: 8 }}>Course</th>
                <th style={{ padding: 8 }}>Stage</th>
                <th style={{ padding: 8 }}>Owner</th>
                <th style={{ padding: 8 }}>SLA</th>
                <th style={{ padding: 8 }}>Days in stage</th>
              </tr>
            </thead>
            <tbody>
              {tableDeals.map((deal) => {
                const contact = contactsById[deal.contact_id];
                const stageIndex = stages.findIndex((s) => s.id === deal.stage_id);
                const stage = stages[stageIndex];
                const daysInStage = Math.floor(
                  (Date.now() - new Date(deal.stage_changed_at).getTime()) / 86_400_000,
                );
                return (
                  <tr
                    key={deal.id}
                    onClick={() => navigate(`/contacts/${deal.contact_id}`)}
                    style={{ cursor: "pointer", borderTop: "1px solid var(--border)" }}
                  >
                    <td style={{ padding: 8 }}>{contact?.full_name ?? "…"}</td>
                    <td style={{ padding: 8 }}>{courseName(deal.course_id) ?? "—"}</td>
                    <td style={{ padding: 8 }}>
                      {stage ? (
                        <Badge
                          label={stage.name}
                          icon={stageIcon(stage)}
                          tone={stageColor(stage, Math.max(stageIndex, 0))}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td style={{ padding: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Avatar name={userDisplayName(users, deal.owner_id)} size={20} />
                        {userDisplayName(users, deal.owner_id)}
                      </div>
                    </td>
                    <td style={{ padding: 8 }}>
                      {deal.sla_state ? (
                        <Badge
                          label={deal.sla_state.replace("_", " ")}
                          tone={SLA_TONE[deal.sla_state]}
                        />
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: 8, color: "var(--text-muted)" }}>{daysInStage}d</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}

        {loaded && view === "table" && visibleDeals.length > 0 && (
          <Pager
            page={tablePage}
            pageSize={tablePageSize}
            total={visibleDeals.length}
            onPageChange={setTablePage}
            onPageSizeChange={setTablePageSize}
          />
        )}
      </div>

      {confirmDrop && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--elevation-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-md)",
            padding: "var(--space-4)",
            display: "flex",
            gap: "var(--space-3)",
            alignItems: "center",
          }}
        >
          <span>Mark as {confirmDrop.stage.name}?</span>
          <Button
            variant="primary"
            onClick={() => {
              void moveDeal(confirmDrop.deal, confirmDrop.stage);
              setConfirmDrop(undefined);
            }}
          >
            Confirm
          </Button>
          <Button variant="secondary" onClick={() => setConfirmDrop(undefined)}>
            Cancel
          </Button>
        </div>
      )}

      {showCreate && contactsById && (
        <PipelineCreateDealEntry onClose={() => setShowCreate(false)} onCreated={load} />
      )}
    </div>
  );
}

function PipelineCreateDealEntry({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const { token } = useAuth();
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Contact[]>([]);
  const [selected, setSelected] = useState<Contact | undefined>(undefined);

  async function handleSearch(value: string) {
    setSearch(value);
    if (!token || value.length < 2) {
      setResults([]);
      return;
    }
    const response = await listContacts(token, { search: value });
    setResults(response.data);
  }

  if (selected) {
    return (
      <CreateDealPanel
        contactId={selected.id}
        onClose={onClose}
        onCreated={() => {
          onCreated();
          onClose();
        }}
      />
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.3)",
        display: "flex",
        justifyContent: "flex-end",
      }}
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 420,
          maxWidth: "100%",
          background: "var(--elevation-2)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "var(--shadow-md)",
          padding: "var(--space-5)",
        }}
      >
        <h1 style={{ fontSize: "var(--text-xl)", lineHeight: "var(--line-xl)" }}>Find a contact</h1>
        <input
          autoFocus
          placeholder="Search contacts…"
          value={search}
          onChange={(event) => void handleSearch(event.target.value)}
          style={{ width: "100%" }}
        />
        <ul style={{ listStyle: "none", padding: 0 }}>
          {results.map((contact) => (
            <li key={contact.id}>
              <Button variant="text" onClick={() => setSelected(contact)}>
                {contact.full_name}
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
