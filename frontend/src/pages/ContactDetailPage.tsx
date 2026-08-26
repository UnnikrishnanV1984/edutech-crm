import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getContact, updateContact, type Contact } from "../api/contacts";
import { updateDeal } from "../api/deals";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { PageSpinner } from "../components/Spinner";
import { leadSourceColor, leadSourceLabel } from "../leadSource";
import { userDisplayName, useUsers } from "../useUsers";
import { useIsMobile } from "../useIsMobile";
import { useMe } from "../useMe";
import { ActivitySection } from "./ActivitySection";
import { CreateTaskPanel } from "./CreateTaskPanel";
import { DealsSection } from "./DealsSection";
import { DocumentsSection } from "./DocumentsSection";
import { FollowUpFlagCard } from "./FollowUpFlagCard";
import { LogActivityPanel } from "./LogActivityPanel";
import { SlaCard } from "./SlaCard";
import { TasksSection } from "./TasksSection";

export function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>();
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const isMobile = useIsMobile();
  const [contact, setContact] = useState<Contact | undefined>(undefined);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [editingTerritory, setEditingTerritory] = useState(false);
  const [territoryDraft, setTerritoryDraft] = useState("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [showLogActivity, setShowLogActivity] = useState(false);
  const [showAddTask, setShowAddTask] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [dealsKey, setDealsKey] = useState(0);
  const [tasksKey, setTasksKey] = useState(0);
  const [activityKey, setActivityKey] = useState(0);
  const [mobileTab, setMobileTab] = useState<"deals" | "tasks" | "activity" | "docs">("deals");

  function loadContact() {
    if (!token || !contactId) return;
    getContact(token, contactId)
      .then((response) => setContact(response.data))
      .catch(() => setError("Couldn't load contact"));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadContact, [token, contactId]);

  useEffect(() => {
    if (!token) return;
    listPipelineStages(token).then((response) => setStages(response.data));
  }, [token]);

  async function saveName() {
    if (!token || !contact) return;
    const previous = contact.full_name;
    setContact({ ...contact, full_name: nameDraft });
    setEditingName(false);
    try {
      await updateContact(token, contact.id, { full_name: nameDraft });
    } catch {
      setContact((current) => (current ? { ...current, full_name: previous } : current));
    }
  }

  async function saveTerritory() {
    if (!token || !contact) return;
    const previous = contact.territory;
    setContact({ ...contact, territory: territoryDraft || null });
    setEditingTerritory(false);
    try {
      await updateContact(token, contact.id, { territory: territoryDraft });
    } catch {
      setContact((current) => (current ? { ...current, territory: previous } : current));
    }
  }

  const currentStageIndex = stages.findIndex((s) => s.id === contact?.stage_id);
  const nextStage =
    currentStageIndex >= 0 && currentStageIndex < stages.length - 1
      ? stages[currentStageIndex + 1]
      : undefined;

  async function advanceStage() {
    if (!token || !contact?.current_deal_id || !nextStage) return;
    setAdvancing(true);
    try {
      await updateDeal(token, contact.current_deal_id, { stage_id: nextStage.id });
      loadContact();
      setDealsKey((k) => k + 1);
      setActivityKey((k) => k + 1);
    } finally {
      setAdvancing(false);
    }
  }

  function refreshAfterActivity() {
    setShowLogActivity(false);
    setActivityKey((k) => k + 1);
  }

  if (error) {
    return (
      <p role="alert" style={{ padding: 24 }}>
        {error}
      </p>
    );
  }

  if (!contact || !contactId) {
    return <PageSpinner />;
  }

  const isBreached = contact.sla_state === "breached";
  const canSeeFollowUpFlag = me?.user.role === "manager" || me?.user.role === "admin";

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "var(--space-6)" }}>
      <div style={{ marginBottom: "var(--space-4)" }}>
        <Link to="/contacts" style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
          Contacts / record
        </Link>
      </div>

      <header style={{ marginBottom: "var(--space-5)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
          {editingName ? (
            <input
              autoFocus
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              onBlur={() => void saveName()}
              onKeyDown={(event) => {
                if (event.key === "Enter") void saveName();
              }}
              style={{ fontSize: 24, fontWeight: 600 }}
            />
          ) : (
            <h1
              onClick={() => {
                setNameDraft(contact.full_name);
                setEditingName(true);
              }}
              style={{ cursor: "text", margin: 0 }}
            >
              {contact.full_name}
            </h1>
          )}
          <Badge label={leadSourceLabel(contact.lead_source)} tone={leadSourceColor(contact.lead_source)} />
          {isBreached && (
            <Badge
              label="SLA breached"
              tone={{ bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" }}
            />
          )}
          <div style={{ flex: 1 }} />
          <Button variant="secondary" onClick={() => setShowLogActivity(true)}>
            Log activity
          </Button>
          <Button variant="secondary" onClick={() => setShowAddTask(true)}>
            Add task
          </Button>
          {!isMobile && (
            <Button
              variant="primary"
              disabled={!nextStage || advancing}
              title={!nextStage ? "No active deal, or already at the final stage" : undefined}
              onClick={() => void advanceStage()}
            >
              {advancing ? "Advancing…" : nextStage ? `Advance to ${nextStage.name}` : "Advance stage"}
            </Button>
          )}
        </div>

        <div style={{ display: "flex", gap: "var(--space-6)", marginTop: "var(--space-4)", flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Owner</div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
              <Avatar name={userDisplayName(users, contact.owner_id)} size={20} />
              {userDisplayName(users, contact.owner_id)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Phone</div>
            <div style={{ marginTop: 4 }}>{contact.phone ?? "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Email</div>
            <div style={{ marginTop: 4 }}>{contact.email ?? "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Territory</div>
            <div style={{ marginTop: 4 }}>
              {editingTerritory ? (
                <input
                  autoFocus
                  value={territoryDraft}
                  onChange={(event) => setTerritoryDraft(event.target.value)}
                  onBlur={() => void saveTerritory()}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void saveTerritory();
                  }}
                  style={{ fontSize: 13, width: 100 }}
                />
              ) : (
                <span
                  onClick={() => {
                    setTerritoryDraft(contact.territory ?? "");
                    setEditingTerritory(true);
                  }}
                  style={{ cursor: "text" }}
                >
                  {contact.territory ?? "—"}
                </span>
              )}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Created</div>
            <div style={{ marginTop: 4 }}>{new Date(contact.created_at).toLocaleDateString()}</div>
          </div>
        </div>
      </header>

      {isMobile ? (
        <div>
          <div className="table-scroll" style={{ display: "flex", borderBottom: "1px solid var(--border)" }}>
            {(
              [
                { value: "deals", label: "Deals" },
                { value: "tasks", label: "Tasks" },
                { value: "activity", label: "Activity" },
                { value: "docs", label: "Docs" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => setMobileTab(tab.value)}
                style={{
                  padding: "8px 14px",
                  border: "none",
                  background: "none",
                  cursor: "pointer",
                  fontSize: "var(--text-sm)",
                  fontWeight:
                    mobileTab === tab.value ? "var(--weight-semibold)" : "var(--weight-normal)",
                  color: mobileTab === tab.value ? "var(--text-h)" : "var(--text-muted)",
                  borderBottom:
                    mobileTab === tab.value ? "2px solid var(--accent)" : "2px solid transparent",
                  marginBottom: -1,
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", marginTop: "var(--space-4)" }}>
            {mobileTab === "deals" && (
              <>
                <SlaCard
                  dealId={contact.current_deal_id}
                  slaState={contact.sla_state}
                  targetAt={contact.sla_target_at}
                  targetMinutes={contact.sla_target_minutes}
                />
                <DealsSection key={dealsKey} contactId={contactId} />
              </>
            )}
            {mobileTab === "tasks" && (
              <>
                <TasksSection key={tasksKey} contactId={contactId} contactName={contact.full_name} />
                {canSeeFollowUpFlag && <FollowUpFlagCard contactId={contactId} />}
              </>
            )}
            {mobileTab === "activity" && <ActivitySection key={activityKey} contactId={contactId} />}
            {mobileTab === "docs" && <DocumentsSection contactId={contactId} />}
          </div>
        </div>
      ) : (
        <div className="contact-detail-grid">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <DealsSection key={dealsKey} contactId={contactId} />
            <ActivitySection key={activityKey} contactId={contactId} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <SlaCard
              dealId={contact.current_deal_id}
              slaState={contact.sla_state}
              targetAt={contact.sla_target_at}
              targetMinutes={contact.sla_target_minutes}
            />
            <TasksSection key={tasksKey} contactId={contactId} contactName={contact.full_name} />
            <DocumentsSection contactId={contactId} />
            {canSeeFollowUpFlag && <FollowUpFlagCard contactId={contactId} />}
          </div>
        </div>
      )}

      {isMobile && (
        <div
          style={{
            position: "sticky",
            bottom: 56,
            marginTop: "var(--space-4)",
            padding: "var(--space-3)",
            background: "var(--elevation-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-md)",
            display: "flex",
            gap: "var(--space-2)",
          }}
        >
          <Button
            variant="primary"
            disabled={!nextStage || advancing}
            title={!nextStage ? "No active deal, or already at the final stage" : undefined}
            onClick={() => void advanceStage()}
            style={{ flex: 1, textAlign: "center" }}
          >
            {advancing ? "Advancing…" : nextStage ? `Advance to ${nextStage.name}` : "Advance stage"}
          </Button>
          <Button variant="secondary" onClick={() => setShowAddTask(true)}>
            + Task
          </Button>
        </div>
      )}

      {showLogActivity && (
        <LogActivityPanel
          contactId={contactId}
          onClose={() => setShowLogActivity(false)}
          onLogged={refreshAfterActivity}
        />
      )}

      {showAddTask && (
        <CreateTaskPanel
          contactId={contactId}
          contactName={contact.full_name}
          onClose={() => setShowAddTask(false)}
          onCreated={() => {
            setShowAddTask(false);
            setTasksKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}
