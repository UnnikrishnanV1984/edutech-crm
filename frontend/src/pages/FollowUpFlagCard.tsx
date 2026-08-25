import { useEffect, useState } from "react";

import { ApiRequestError } from "../api/client";
import {
  createFollowUpFlag,
  listFollowUpFlags,
  resolveFollowUpFlag,
  type FollowUpFlag,
} from "../api/followUpFlags";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";

const ACCENT_TINT = { bg: "var(--accent-subtle)", fg: "var(--accent-hover)", border: "var(--accent)" };

// Manager/admin only (REQUIREMENTS.md §4.3 — "a Manager can place a
// follow-up flag... it's the manager's own tracking tool"), matching the
// same require_manager_or_admin gate the backend already enforces.
interface FollowUpFlagCardProps {
  contactId: string;
}

export function FollowUpFlagCard({ contactId }: FollowUpFlagCardProps) {
  const { token } = useAuth();
  const [flags, setFlags] = useState<FollowUpFlag[] | undefined>(undefined);
  const [showCreate, setShowCreate] = useState(false);
  const [note, setNote] = useState("");
  const [remindOn, setRemindOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listFollowUpFlags(token, { contact_id: contactId }).then((response) => setFlags(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, contactId]);

  const openFlag = flags?.find((f) => !f.resolved_at);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !note.trim() || !remindOn) return;
    setBusy(true);
    setError(undefined);
    try {
      await createFollowUpFlag(token, { contact_id: contactId, note: note.trim(), remind_on: remindOn });
      setShowCreate(false);
      setNote("");
      setRemindOn("");
      load();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't create follow-up flag");
    } finally {
      setBusy(false);
    }
  }

  async function handleClear() {
    if (!token || !openFlag) return;
    setBusy(true);
    try {
      await resolveFollowUpFlag(token, openFlag.id);
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <span
        style={{
          fontSize: 10,
          fontWeight: "var(--weight-semibold)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--text-muted)",
        }}
      >
        Follow-up flag
      </span>

      {flags === undefined && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <Spinner size={16} />
        </div>
      )}

      {flags && (
        <div style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", gap: 6 }}>
            <Badge label={openFlag ? "Flagged" : "Clear"} tone={openFlag ? ACCENT_TINT : undefined} />
            {openFlag && (
              <Button variant="text" disabled={busy} onClick={() => void handleClear()}>
                Clear
              </Button>
            )}
          </div>
          {openFlag && (
            <div style={{ fontSize: "var(--text-sm)" }}>
              <div>{openFlag.note}</div>
              <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>
                Remind on {new Date(openFlag.remind_on).toLocaleDateString()}
              </div>
            </div>
          )}
          {!openFlag && !showCreate && (
            <Button variant="secondary" onClick={() => setShowCreate(true)}>
              + Flag for follow-up
            </Button>
          )}
        </div>
      )}

      {showCreate && (
        <form
          onSubmit={(event) => {
            void handleCreate(event);
          }}
          style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
        >
          <textarea
            required
            autoFocus
            rows={2}
            placeholder="Why check on this personally?"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            style={{ width: "100%" }}
          />
          <input
            required
            type="date"
            value={remindOn}
            onChange={(event) => setRemindOn(event.target.value)}
          />
          {error && (
            <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)", margin: 0 }}>
              {error}
            </p>
          )}
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button variant="primary" type="submit" disabled={busy || !note.trim() || !remindOn}>
              {busy ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Spinner size={12} /> Saving…
                </span>
              ) : (
                "Save"
              )}
            </Button>
            <Button variant="text" type="button" disabled={busy} onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
