import { useState } from "react";

import { listContacts, type Contact } from "../api/contacts";
import { createTask, type Task } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { useUsers } from "../useUsers";

interface CreateTaskPanelProps {
  contactId?: string;
  contactName?: string;
  dealId?: string;
  onClose: () => void;
  onCreated: (task: Task) => void;
}

export function CreateTaskPanel({
  contactId,
  contactName,
  dealId,
  onClose,
  onCreated,
}: CreateTaskPanelProps) {
  const { token } = useAuth();
  const users = useUsers();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [contactSearch, setContactSearch] = useState("");
  const [contactResults, setContactResults] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<
    { id: string; name: string } | undefined
  >(contactId && contactName ? { id: contactId, name: contactName } : undefined);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleContactSearch(value: string) {
    setContactSearch(value);
    if (!token || value.length < 2) {
      setContactResults([]);
      return;
    }
    const response = await listContacts(token, { search: value });
    setContactResults(response.data);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !selectedContact) {
      return;
    }
    setSubmitting(true);
    setError(undefined);
    try {
      const response = await createTask(token, {
        contact_id: selectedContact.id,
        deal_id: dealId,
        assignee_id: assigneeId || undefined,
        title,
        description: description || undefined,
        due_at: dueAt ? new Date(dueAt).toISOString() : undefined,
      });
      onCreated(response.data);
    } catch {
      setError("Couldn't create task — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="New Task" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        {!contactId && (
          <label>
            Contact*
            {selectedContact ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
                <span>{selectedContact.name}</span>
                <Button
                  variant="text"
                  type="button"
                  onClick={() => setSelectedContact(undefined)}
                >
                  Change
                </Button>
              </div>
            ) : (
              <>
                <input
                  placeholder="Search contacts…"
                  value={contactSearch}
                  onChange={(event) => {
                    void handleContactSearch(event.target.value);
                  }}
                  style={{ display: "block", width: "100%", marginTop: 4 }}
                />
                {contactResults.length > 0 && (
                  <ul style={{ listStyle: "none", padding: 0, margin: "4px 0 0" }}>
                    {contactResults.map((contact) => (
                      <li key={contact.id}>
                        <Button
                          variant="text"
                          type="button"
                          onClick={() =>
                            setSelectedContact({ id: contact.id, name: contact.full_name })
                          }
                        >
                          {contact.full_name}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </label>
        )}
        <label>
          Title*
          <input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Description
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Assignee
          <select
            value={assigneeId}
            onChange={(event) => setAssigneeId(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            <option value="">Me</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name ?? user.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Due date
          <input
            type="datetime-local"
            value={dueAt}
            onChange={(event) => setDueAt(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={submitting || !selectedContact}>
            {submitting ? "Creating…" : "Create Task"}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
