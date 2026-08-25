import { useState } from "react";

import { ApiRequestError } from "../api/client";
import { logActivity, type Activity, type ActivityChannel } from "../api/contacts";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { Spinner } from "../components/Spinner";

const CHANNELS: { value: ActivityChannel; label: string }[] = [
  { value: "call", label: "Call" },
  { value: "email", label: "Email" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "note", label: "Note" },
];

interface LogActivityPanelProps {
  contactId: string;
  onClose: () => void;
  onLogged: (activity: Activity) => void;
}

export function LogActivityPanel({ contactId, onClose, onLogged }: LogActivityPanelProps) {
  const { token } = useAuth();
  const [channel, setChannel] = useState<ActivityChannel>("call");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !note.trim()) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const response = await logActivity(token, contactId, { note: note.trim(), channel });
      onLogged(response.data);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't log activity");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="Log activity" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <label>
          Channel
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            {CHANNELS.map((option) => (
              <Button
                key={option.value}
                type="button"
                variant={channel === option.value ? "primary" : "secondary"}
                onClick={() => setChannel(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </label>
        <label>
          Note*
          <textarea
            required
            autoFocus
            rows={5}
            value={note}
            onChange={(event) => setNote(event.target.value)}
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
          <Button variant="primary" type="submit" disabled={submitting || !note.trim()}>
            {submitting ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> Logging…
              </span>
            ) : (
              "Log activity"
            )}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
