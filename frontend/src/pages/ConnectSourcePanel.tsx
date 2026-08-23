import { useState } from "react";

import {
  createConnection,
  type LeadSource,
  type LeadSourceConnection,
} from "../api/leadSourceConnections";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";

interface ConnectSourcePanelProps {
  onClose: () => void;
  onCreated: (connection: LeadSourceConnection) => void;
}

const SOURCES: { value: LeadSource; label: string }[] = [
  { value: "meta", label: "Meta Lead Ads" },
  { value: "google", label: "Google Ads" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "web", label: "Web form" },
];

export function ConnectSourcePanel({ onClose, onCreated }: ConnectSourcePanelProps) {
  const { token } = useAuth();
  const [source, setSource] = useState<LeadSource>("meta");
  const [externalAccountId, setExternalAccountId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const needsCredentials = source !== "web";

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const response = await createConnection(token, {
        source,
        external_account_id: needsCredentials ? externalAccountId : undefined,
        access_token: needsCredentials ? accessToken : undefined,
        refresh_token: needsCredentials && refreshToken ? refreshToken : undefined,
      });
      onCreated(response.data);
    } catch {
      setError("Couldn't connect — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="Connect a lead source" onClose={onClose}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <label>
          Source*
          <select
            value={source}
            onChange={(event) => setSource(event.target.value as LeadSource)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>

        {source === "web" ? (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
            An embeddable form key is generated automatically once connected — no credentials
            needed for this source.
          </p>
        ) : (
          <>
            <label>
              {source === "meta" && "Page ID*"}
              {source === "whatsapp" && "Phone number ID*"}
              {source === "google" && "Customer ID*"}
              <input
                required
                value={externalAccountId}
                onChange={(event) => setExternalAccountId(event.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <label>
              Access token*
              <input
                required
                type="password"
                value={accessToken}
                onChange={(event) => setAccessToken(event.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            {source === "google" && (
              <label>
                Refresh token
                <input
                  type="password"
                  value={refreshToken}
                  onChange={(event) => setRefreshToken(event.target.value)}
                  style={{ display: "block", width: "100%", marginTop: 4 }}
                />
              </label>
            )}
          </>
        )}

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
            {submitting ? "Connecting…" : "Connect"}
          </Button>
        </div>
      </form>
    </SlideOverPanel>
  );
}
