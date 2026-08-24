import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getContact, updateContact, type Contact } from "../api/contacts";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { leadSourceColor, leadSourceLabel } from "../leadSource";
import { userDisplayName, useUsers } from "../useUsers";
import { ActivitySection } from "./ActivitySection";
import { DealsSection } from "./DealsSection";
import { DocumentsSection } from "./DocumentsSection";
import { TasksSection } from "./TasksSection";

export function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>();
  const { token } = useAuth();
  const users = useUsers();
  const [contact, setContact] = useState<Contact | undefined>(undefined);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [editingTerritory, setEditingTerritory] = useState(false);
  const [territoryDraft, setTerritoryDraft] = useState("");
  const [error, setError] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!token || !contactId) return;
    getContact(token, contactId)
      .then((response) => setContact(response.data))
      .catch(() => setError("Couldn't load contact"));
  }, [token, contactId]);

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

  if (error) {
    return (
      <p role="alert" style={{ padding: 24 }}>
        {error}
      </p>
    );
  }

  if (!contact || !contactId) {
    return <p style={{ padding: 24 }}>Loading…</p>;
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
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
            style={{ cursor: "text" }}
          >
            {contact.full_name}
          </h1>
        )}
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
          <Badge
            label={leadSourceLabel(contact.lead_source)}
            tone={leadSourceColor(contact.lead_source)}
          />
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Owner: {userDisplayName(users, contact.owner_id)}
          </span>
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Territory:{" "}
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
          </span>
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Created {new Date(contact.created_at).toLocaleDateString()}
          </span>
        </div>
      </header>

      <div className="contact-detail-grid">
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <DealsSection contactId={contactId} />
          <ActivitySection contactId={contactId} hasDeals />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <TasksSection contactId={contactId} contactName={contact.full_name} />
          <DocumentsSection contactId={contactId} />
        </div>
      </div>
    </div>
  );
}
