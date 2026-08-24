import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getContact, listContacts, type Contact } from "../api/contacts";
import { listCourses, type Course } from "../api/courses";
import { listDeals, updateDeal, type Deal } from "../api/deals";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Avatar } from "../components/Avatar";
import { Button } from "../components/Button";
import { OwnerFilter } from "../components/OwnerFilter";
import { useToast } from "../components/toastContext";
import { defaultOwnerFilterValue } from "../ownerFilter";
import { stageColor, stageIcon } from "../stageColor";
import { userDisplayName, useUsers } from "../useUsers";
import { useMe } from "../useMe";
import { CreateDealPanel } from "./CreateDealPanel";

export function PipelinePage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [contactsById, setContactsById] = useState<Record<string, Contact>>({});
  // undefined = "my team" (manager) or "everyone" (admin), per
  // ADMIN_UX_IMPROVEMENTS_PLAN.md Sec5 — same OwnerFilter contract as
  // TasksPage.tsx.
  const [ownerId, setOwnerId] = useState<string | undefined>(undefined);
  const [draggingDealId, setDraggingDealId] = useState<string | undefined>(undefined);
  const [confirmDrop, setConfirmDrop] = useState<{ deal: Deal; stage: PipelineStage } | undefined>(
    undefined,
  );
  const [showCreate, setShowCreate] = useState(false);

  function load() {
    if (!token) return;
    listPipelineStages(token).then((response) => setStages(response.data));
    listCourses(token).then((response) => setCourses(response.data));
    listDeals(token, {
      owner_id: me?.user.role === "counselor" ? undefined : ownerId,
      page_size: 100,
    }).then(
      (response) => {
        setDeals(response.data);
        const missing = [...new Set(response.data.map((d) => d.contact_id))].filter(
          (id) => !(id in contactsById),
        );
        Promise.all(missing.map((id) => getContact(token, id))).then((results) => {
          setContactsById((current) => {
            const next = { ...current };
            for (const r of results) next[r.data.id] = r.data;
            return next;
          });
        });
      },
    );
  }

  useEffect(() => {
    if (me) setOwnerId(defaultOwnerFilterValue(me.user.role, me.user.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user.id, me?.user.role]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, ownerId, me]);

  function courseName(courseId: string) {
    return courses.find((c) => c.id === courseId)?.name ?? "";
  }

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
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h1>Pipeline</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
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
            + New Deal
          </Button>
        </div>
      </div>

      <div className="pipeline-columns">
        {stages.map((stage, index) => {
          const tone = stageColor(stage, index);
          const columnDeals = deals.filter((d) => d.stage_id === stage.id);
          return (
            <div
              key={stage.id}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => handleDrop(stage)}
              style={{
                width: 280,
                flexShrink: 0,
                background: "var(--surface)",
                borderRadius: "var(--radius)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  borderTop: `3px solid ${tone.fg}`,
                  borderRadius: "var(--radius) var(--radius) 0 0",
                  padding: "var(--space-2)",
                  display: "flex",
                  justifyContent: "space-between",
                  fontWeight: "var(--weight-semibold)",
                }}
              >
                <span>
                  {stageIcon(stage)} {stage.name}
                </span>
                <span style={{ color: "var(--text-muted)" }}>{columnDeals.length}</span>
              </div>
              <div
                style={{
                  padding: "var(--space-2)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-2)",
                }}
              >
                {columnDeals.map((deal) => {
                  const contact = contactsById[deal.contact_id];
                  const daysInStage = Math.floor(
                    (Date.now() - new Date(deal.stage_changed_at).getTime()) / 86_400_000,
                  );
                  const dragging = draggingDealId === deal.id;
                  return (
                    <div
                      key={deal.id}
                      draggable
                      onDragStart={() => setDraggingDealId(deal.id)}
                      onDragEnd={() => setDraggingDealId(undefined)}
                      onClick={() => navigate(`/contacts/${deal.contact_id}`)}
                      style={{
                        background: "var(--elevation-2)",
                        borderLeft: `3px solid ${tone.fg}`,
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius)",
                        padding: "var(--space-2)",
                        cursor: "grab",
                        boxShadow: dragging ? "var(--shadow-lg)" : undefined,
                        transform: dragging ? "scale(1.02)" : undefined,
                        transition: "box-shadow 120ms ease, transform 120ms ease",
                      }}
                    >
                      <div style={{ fontWeight: "var(--weight-semibold)" }}>
                        {contact?.full_name ?? "…"}
                      </div>
                      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                        {courseName(deal.course_id)}
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginTop: 4,
                        }}
                      >
                        <Avatar name={userDisplayName(users, deal.owner_id)} size={18} />
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                          {daysInStage}d
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
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
