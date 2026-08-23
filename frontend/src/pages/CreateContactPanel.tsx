import { useState } from "react";

import { ApiRequestError } from "../api/client";
import { createContact, getContact, type Contact } from "../api/contacts";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { useUsers } from "../useUsers";

interface CreateContactPanelProps {
  onClose: () => void;
  onCreated: (contact: Contact) => void;
}

const LEAD_SOURCES = ["meta", "google", "web", "whatsapp", "manual"];

export function CreateContactPanel({ onClose, onCreated }: CreateContactPanelProps) {
  const { token } = useAuth();
  const users = useUsers();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [leadSource, setLeadSource] = useState("web");
  const [ownerId, setOwnerId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | undefined>(undefined);
  const [duplicate, setDuplicate] = useState<Contact | undefined>(undefined);

  if (!token) {
    return null;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFieldError(undefined);
    try {
      const response = await createContact(token!, {
        full_name: fullName,
        email: email || undefined,
        phone: phone || undefined,
        lead_source: leadSource,
        owner_id: ownerId || undefined,
      });
      onCreated(response.data);
    } catch (err) {
      if (err instanceof ApiRequestError && err.code === "CONFLICT") {
        const existingId = err.details?.[0]?.existing_contact_id;
        if (typeof existingId === "string") {
          const existing = await getContact(token!, existingId);
          setDuplicate(existing.data);
        }
      } else if (err instanceof ApiRequestError) {
        setFieldError(err.message);
      } else {
        setFieldError("Something went wrong — try again");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (duplicate) {
    return (
      <SlideOverPanel title="New Contact" onClose={onClose}>
        <p style={{ fontWeight: 600 }}>We found a possible duplicate</p>
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 12,
          }}
        >
          <div>{duplicate.full_name}</div>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            {duplicate.email ?? duplicate.phone}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="primary" type="button" onClick={() => onCreated(duplicate)}>
            Open existing contact
          </Button>
          <Button variant="secondary" type="button" onClick={() => setDuplicate(undefined)}>
            Go back
          </Button>
        </div>
      </SlideOverPanel>
    );
  }

  return (
    <SlideOverPanel title="New Contact" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <label>
          Full name*
          <input
            required
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Phone
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Lead source
          <select
            value={leadSource}
            onChange={(event) => setLeadSource(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {LEAD_SOURCES.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </label>
        <label>
          Owner
          <select
            value={ownerId}
            onChange={(event) => setOwnerId(event.target.value)}
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
        {fieldError && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {fieldError}
          </p>
        )}
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create Contact"}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
