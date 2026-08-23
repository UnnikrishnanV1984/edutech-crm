import { useEffect, useState } from "react";

import {
  listConnections,
  setConnectionStatus,
  syncConnection,
  type LeadSourceConnection,
} from "../api/leadSourceConnections";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { useMe } from "../useMe";
import { ConnectSourcePanel } from "./ConnectSourcePanel";

const SOURCE_LABELS: Record<string, string> = {
  meta: "Meta Lead Ads",
  google: "Google Ads",
  whatsapp: "WhatsApp",
  web: "Web form",
};

export function IntegrationsPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [connections, setConnections] = useState<LeadSourceConnection[]>([]);
  const [showConnect, setShowConnect] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listConnections(token).then((response) => setConnections(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role !== "admin") {
    return (
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
        <EmptyState headline="Admins only" subtext="Ask a tenant admin to manage integrations." />
      </div>
    );
  }

  async function toggleStatus(connection: LeadSourceConnection) {
    if (!token) return;
    setBusyId(connection.id);
    const nextStatus = connection.status === "active" ? "disabled" : "active";
    try {
      const response = await setConnectionStatus(token, connection.id, nextStatus);
      setConnections((current) =>
        current.map((c) => (c.id === connection.id ? response.data : c)),
      );
    } finally {
      setBusyId(undefined);
    }
  }

  async function sync(connection: LeadSourceConnection) {
    if (!token) return;
    setBusyId(connection.id);
    try {
      await syncConnection(token, connection.id);
      load();
    } finally {
      setBusyId(undefined);
    }
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h1>Integrations</h1>
        <Button variant="primary" onClick={() => setShowConnect(true)}>
          + Connect
        </Button>
      </div>

      {connections.length === 0 && (
        <EmptyState
          headline="No lead sources connected"
          subtext="Connect Meta, Google, WhatsApp, or a web form to start capturing leads automatically."
          action={
            <Button variant="primary" onClick={() => setShowConnect(true)}>
              + Connect a source
            </Button>
          }
        />
      )}

      {connections.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: 8 }}>Source</th>
              <th style={{ padding: 8 }}>Account</th>
              <th style={{ padding: 8 }}>Status</th>
              <th style={{ padding: 8 }}>Last synced</th>
              <th style={{ padding: 8 }}></th>
            </tr>
          </thead>
          <tbody>
            {connections.map((connection) => (
              <tr key={connection.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: 8 }}>{SOURCE_LABELS[connection.source]}</td>
                <td style={{ padding: 8, fontFamily: "monospace", fontSize: 12 }}>
                  {connection.external_account_id}
                </td>
                <td style={{ padding: 8 }}>
                  <Badge
                    variant="chip"
                    label={connection.status}
                    tone={
                      connection.status === "active"
                        ? { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" }
                        : { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" }
                    }
                  />
                </td>
                <td style={{ padding: 8, color: "var(--text-muted)", fontSize: 13 }}>
                  {connection.last_synced_at
                    ? new Date(connection.last_synced_at).toLocaleString()
                    : "Never"}
                </td>
                <td style={{ padding: 8, display: "flex", gap: 8, justifyContent: "flex-end" }}>
                  {connection.source === "google" && connection.status === "active" && (
                    <Button
                      variant="text"
                      disabled={busyId === connection.id}
                      onClick={() => void sync(connection)}
                    >
                      Sync now
                    </Button>
                  )}
                  <Button
                    variant="text"
                    disabled={busyId === connection.id}
                    onClick={() => void toggleStatus(connection)}
                  >
                    {connection.status === "active" ? "Disconnect" : "Reconnect"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showConnect && (
        <ConnectSourcePanel
          onClose={() => setShowConnect(false)}
          onCreated={() => {
            setShowConnect(false);
            load();
          }}
        />
      )}
    </div>
  );
}
