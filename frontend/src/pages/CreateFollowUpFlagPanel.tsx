import { useState } from "react";

import { createFollowUpFlag, type FollowUpFlag } from "../api/followUpFlags";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { Spinner } from "../components/Spinner";

interface CreateFollowUpFlagPanelProps {
  onClose: () => void;
  onCreated: (flag: FollowUpFlag) => void;
}

export function CreateFollowUpFlagPanel({ onClose, onCreated }: CreateFollowUpFlagPanelProps) {
  const { token } = useAuth();
  const [contactId, setContactId] = useState("");
  const [note, setNote] = useState("");
  const [remindOn, setRemindOn] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const response = await createFollowUpFlag(token, {
        contact_id: contactId,
        note,
        remind_on: remindOn,
      });
      onCreated(response.data);
    } catch {
      setError("Couldn't create follow-up — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="New follow-up" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <label>
          Contact ID*
          <input
            required
            value={contactId}
            onChange={(event) => setContactId(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Note*
          <textarea
            required
            value={note}
            onChange={(event) => setNote(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          Remind on*
          <input
            required
            type="date"
            value={remindOn}
            onChange={(event) => setRemindOn(event.target.value)}
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
          <Button variant="primary" type="submit" disabled={submitting}>
            {submitting ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> Saving…
              </span>
            ) : (
              "Save"
            )}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
