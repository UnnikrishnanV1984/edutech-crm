import { Fragment, useEffect, useState } from "react";

import {
  listConnections,
  setConnectionStatus,
  setConversionTargetId,
  syncConnection,
  type LeadSourceConnection,
} from "../api/leadSourceConnections";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { config } from "../config";
import { useMe } from "../useMe";
import { ConnectSourcePanel } from "./ConnectSourcePanel";

// GAP_FIXES_PLAN.md item 2 — the ingestion endpoint (POST /webhooks/web)
// already exists and is real; this is the missing piece, an actual
// snippet a tenant can drop onto their own landing page. Framework-free
// on purpose — it has to run on an arbitrary external page, not just
// inside this app.
function buildEmbedSnippet(embedKey: string): string {
  return `<form id="edutech-crm-lead-form">
  <input name="full_name" placeholder="Full name" required />
  <input name="email" type="email" placeholder="Email" />
  <input name="phone" placeholder="Phone" />
  <button type="submit">Submit</button>
</form>
<script>
(function () {
  var form = document.getElementById("edutech-crm-lead-form");
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var data = new FormData(form);
    fetch("${config.backendPublicUrl}/webhooks/web", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        embed_key: "${embedKey}",
        full_name: data.get("full_name"),
        email: data.get("email") || undefined,
        phone: data.get("phone") || undefined,
      }),
    }).then(function (response) {
      if (response.ok) {
        form.innerHTML = "<p>Thanks — we will be in touch.</p>";
      }
    });
  });
})();
</script>`;
}

const SOURCE_LABELS: Record<string, string> = {
  meta: "Meta Lead Ads",
  google: "Google Ads",
  whatsapp: "WhatsApp",
  web: "Web form",
};

export function IntegrationsPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [connections, setConnections] = useState<LeadSourceConnection[] | undefined>(undefined);
  const [showConnect, setShowConnect] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);
  const [expandedEmbedId, setExpandedEmbedId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listConnections(token).then((response) => setConnections(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role !== "admin") {
    return (
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
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
        current?.map((c) => (c.id === connection.id ? response.data : c)),
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

  async function saveConversionTarget(connection: LeadSourceConnection, value: string) {
    if (!token) return;
    setBusyId(connection.id);
    try {
      const response = await setConversionTargetId(token, connection.id, value);
      setConnections((current) =>
        current?.map((c) => (c.id === connection.id ? response.data : c)),
      );
    } finally {
      setBusyId(undefined);
    }
  }

  return (
    <>

      <Card
        title="Connected sources"
        action={
          <Button variant="primary" onClick={() => setShowConnect(true)}>
            + Connect
          </Button>
        }
      >
        {connections === undefined && <PageSpinner />}

        {connections && connections.length === 0 && (
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

        {connections && connections.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "var(--space-2)" }}>Source</th>
                <th style={{ padding: "var(--space-2)" }}>Account</th>
                <th style={{ padding: "var(--space-2)" }}>Status</th>
                <th style={{ padding: "var(--space-2)" }}>Conversion target</th>
                <th style={{ padding: "var(--space-2)" }}>Last synced</th>
                <th style={{ padding: "var(--space-2)" }}></th>
              </tr>
            </thead>
            <tbody>
              {connections.map((connection) => (
                <Fragment key={connection.id}>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "var(--space-2)" }}>{SOURCE_LABELS[connection.source]}</td>
                  <td style={{ padding: "var(--space-2)", fontFamily: "monospace", fontSize: 12 }}>
                    {connection.external_account_id}
                  </td>
                  <td style={{ padding: "var(--space-2)" }}>
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
                  <td style={{ padding: "var(--space-2)" }}>
                    {connection.source === "meta" || connection.source === "google" ? (
                      <ConversionTargetCell
                        connection={connection}
                        busy={busyId === connection.id}
                        onSave={(value) => void saveConversionTarget(connection, value)}
                      />
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: 13 }}>
                    {connection.last_synced_at
                      ? new Date(connection.last_synced_at).toLocaleString()
                      : "Never"}
                  </td>
                  <td style={{ padding: "var(--space-2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    {connection.source === "web" && (
                      <Button
                        variant="text"
                        onClick={() =>
                          setExpandedEmbedId((current) =>
                            current === connection.id ? undefined : connection.id,
                          )
                        }
                      >
                        {expandedEmbedId === connection.id ? "Hide embed code" : "Get embed code"}
                      </Button>
                    )}
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
                {expandedEmbedId === connection.id && (
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <td colSpan={6} style={{ padding: "var(--space-2)" }}>
                      <EmbedSnippetBlock embedKey={connection.external_account_id} />
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {showConnect && (
        <ConnectSourcePanel
          onClose={() => setShowConnect(false)}
          onCreated={() => {
            setShowConnect(false);
            load();
          }}
        />
      )}
    </>
  );
}

function EmbedSnippetBlock({ embedKey }: { embedKey: string }) {
  const [copied, setCopied] = useState(false);
  const snippet = buildEmbedSnippet(embedKey);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
        Paste this into your landing page's HTML. No credentials needed — the embed key above is
        the only "secret", and it can only submit leads, never read data.
      </p>
      <textarea
        readOnly
        value={snippet}
        rows={12}
        style={{
          width: "100%",
          fontFamily: "monospace",
          fontSize: 12,
          resize: "vertical",
        }}
        onClick={(event) => event.currentTarget.select()}
      />
      <Button
        variant="secondary"
        onClick={() => {
          void navigator.clipboard.writeText(snippet).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          });
        }}
        style={{ alignSelf: "flex-start" }}
      >
        {copied ? "Copied!" : "Copy to clipboard"}
      </Button>
    </div>
  );
}

// Inline click-to-edit rather than a separate panel — a single optional
// identifier per connection (the Meta Pixel/Dataset ID or Google
// conversion action resource name, ARCHITECTURE.md §7d) doesn't warrant
// its own form/panel the way connecting a whole new source does.
function ConversionTargetCell({
  connection,
  busy,
  onSave,
}: {
  connection: LeadSourceConnection;
  busy: boolean;
  onSave: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(connection.conversion_target_id ?? "");

  if (!editing) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span style={{ fontFamily: "monospace", fontSize: 12 }}>
          {connection.conversion_target_id ?? (
            <span style={{ color: "var(--text-muted)", fontFamily: "inherit" }}>Not set</span>
          )}
        </span>
        <Button
          variant="text"
          disabled={busy}
          onClick={() => {
            setValue(connection.conversion_target_id ?? "");
            setEditing(true);
          }}
        >
          Edit
        </Button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Pixel/Dataset ID or conversion action"
        style={{ fontSize: 12, width: 200 }}
      />
      <Button
        variant="primary"
        disabled={busy || !value.trim()}
        onClick={() => {
          onSave(value.trim());
          setEditing(false);
        }}
      >
        Save
      </Button>
      <Button variant="text" disabled={busy} onClick={() => setEditing(false)}>
        Cancel
      </Button>
    </div>
  );
}
