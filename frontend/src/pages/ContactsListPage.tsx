import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listContacts, type Contact } from "../api/contacts";
import { useAuth } from "../auth/context";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { Skeleton } from "../components/Skeleton";
import { leadSourceColor, leadSourceLabel } from "../leadSource";
import { relativeTime } from "../relativeTime";
import { userDisplayName, useUsers } from "../useUsers";
import { useMe } from "../useMe";
import { CreateContactPanel } from "./CreateContactPanel";

const PAGE_SIZE = 25;

export function ContactsListPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const users = useUsers();
  const navigate = useNavigate();

  const [contacts, setContacts] = useState<Contact[] | undefined>(undefined);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [leadSource, setLeadSource] = useState("");
  const [onlyMine, setOnlyMine] = useState(true);
  const [error, setError] = useState<string | undefined>(undefined);
  const [showCreatePanel, setShowCreatePanel] = useState(false);

  function load() {
    if (!token) {
      return;
    }
    setError(undefined);
    listContacts(token, {
      search: search || undefined,
      lead_source: leadSource || undefined,
      owner_id: onlyMine && me ? me.user.id : undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((response) => {
        setContacts(response.data);
        setTotal(response.meta.total);
      })
      .catch(() => setError("Couldn't load contacts"));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, search, leadSource, onlyMine, me, page]);

  function updateFilter(update: () => void) {
    update();
    setPage(1);
  }

  const hasFilters = Boolean(search || leadSource || onlyMine);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <h1>Contacts</h1>
        <Button variant="primary" onClick={() => setShowCreatePanel(true)}>
          + New Contact
        </Button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <input
          placeholder="Search name, email, phone"
          value={search}
          onChange={(event) => updateFilter(() => setSearch(event.target.value))}
        />
        <select
          value={leadSource}
          onChange={(event) => updateFilter(() => setLeadSource(event.target.value))}
        >
          <option value="">All sources</option>
          <option value="meta">Meta</option>
          <option value="google">Google</option>
          <option value="web">Web</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="manual">Manual</option>
        </select>
        <Button
          variant={onlyMine ? "primary" : "secondary"}
          onClick={() => updateFilter(() => setOnlyMine((current) => !current))}
        >
          {onlyMine ? "Mine" : "Everyone"}
        </Button>
      </div>

      {error && (
        <div style={{ marginBottom: 16 }}>
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
          <Button onClick={load}>Retry</Button>
        </div>
      )}

      {!error && contacts === undefined && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} height={32} />
          ))}
        </div>
      )}

      {!error && contacts && contacts.length === 0 && !hasFilters && (
        <EmptyState
          headline="No leads yet"
          subtext="Create your first contact to get started."
          action={
            <Button variant="primary" onClick={() => setShowCreatePanel(true)}>
              New Contact
            </Button>
          }
        />
      )}

      {!error && contacts && contacts.length === 0 && hasFilters && (
        <EmptyState
          headline="No contacts match your filters"
          action={
            <Button
              onClick={() =>
                updateFilter(() => {
                  setSearch("");
                  setLeadSource("");
                  setOnlyMine(false);
                })
              }
            >
              Clear filters
            </Button>
          }
        />
      )}

      {!error && contacts && contacts.length > 0 && (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 13 }}>
                <th style={{ padding: 8 }}>Name</th>
                <th style={{ padding: 8 }}>Lead source</th>
                <th style={{ padding: 8 }}>Owner</th>
                <th style={{ padding: 8 }}>Updated</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((contact) => (
                <tr
                  key={contact.id}
                  onClick={() => navigate(`/contacts/${contact.id}`)}
                  style={{ cursor: "pointer", borderTop: "1px solid var(--border)" }}
                >
                  <td style={{ padding: 8 }}>{contact.full_name}</td>
                  <td style={{ padding: 8 }}>
                    <Badge
                      label={leadSourceLabel(contact.lead_source)}
                      tone={leadSourceColor(contact.lead_source)}
                    />
                  </td>
                  <td style={{ padding: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Avatar name={userDisplayName(users, contact.owner_id)} size={20} />
                      {userDisplayName(users, contact.owner_id)}
                    </div>
                  </td>
                  <td style={{ padding: 8, color: "var(--text-muted)" }}>
                    {relativeTime(contact.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "center" }}>
              <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <span>
                Page {page} of {totalPages}
              </span>
              <Button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {showCreatePanel && (
        <CreateContactPanel
          onClose={() => setShowCreatePanel(false)}
          onCreated={(contact) => navigate(`/contacts/${contact.id}`)}
        />
      )}
    </div>
  );
}
