import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listConnections, type LeadSourceConnection } from "../api/leadSourceConnections";
import { getForecast, getFunnel, getSourceAttribution } from "../api/reports";
import type { ForecastReport, FunnelRow, SourceAttributionRow } from "../api/reports";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";

export function AdminDashboard() {
  const { token } = useAuth();
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [sources, setSources] = useState<SourceAttributionRow[]>([]);
  const [forecast, setForecast] = useState<ForecastReport | undefined>(undefined);
  const [connections, setConnections] = useState<LeadSourceConnection[]>([]);

  useEffect(() => {
    if (!token) return;
    getFunnel(token).then((response) => setFunnel(response.data));
    getSourceAttribution(token).then((response) => setSources(response.data));
    getForecast(token).then((response) => setForecast(response.data));
    listConnections(token).then((response) => setConnections(response.data));
  }, [token]);

  const maxCount = Math.max(1, ...funnel.map((f) => f.count));

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1>Admin dashboard</h1>
        <div style={{ display: "flex", gap: 16, fontSize: 13 }}>
          <Link to="/sla-policies">SLA policies →</Link>
          <Link to="/workflow-rules">Workflow rules →</Link>
          <Link to="/integrations">Integrations →</Link>
        </div>
      </div>

      <div style={{ display: "flex", gap: 32, marginTop: 16 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Org funnel</h2>
          {funnel.length === 0 && <EmptyState headline="No deals yet" />}
          {funnel.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {funnel.map((row) => (
                <div key={row.stage_id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 140, fontSize: 13 }}>{row.stage_name}</span>
                  <div
                    style={{
                      height: 14,
                      borderRadius: "var(--radius-sm)",
                      background: "var(--accent-subtle)",
                      width: `${(row.count / maxCount) * 100}%`,
                      minWidth: row.count > 0 ? 4 : 0,
                    }}
                  />
                  <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{row.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Leads by source</h2>
          {sources.length === 0 && <EmptyState headline="No leads yet" />}
          {sources.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0 }}>
              {sources.map((row) => (
                <li
                  key={row.lead_source}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "4px 0",
                    fontSize: 14,
                  }}
                >
                  <span>{row.lead_source}</span>
                  <span style={{ color: "var(--text-muted)" }}>{row.count}</span>
                </li>
              ))}
            </ul>
          )}
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Lead counts only — cost-per-enrollment needs ad-spend tracking this
            build doesn't have yet.
          </p>
        </div>
      </div>

      {forecast && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>
            Forecast — {forecast.expected_enrollments} expected enrollments
          </h2>
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Weighted headcount, not revenue — set win probabilities per stage
            to refine this.
          </p>
        </div>
      )}

      <h2 style={{ fontSize: 16, marginTop: 24, marginBottom: 8 }}>Integration health</h2>
      {connections.length === 0 && <EmptyState headline="No sources connected" />}
      {connections.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: 8 }}>Source</th>
              <th style={{ padding: 8 }}>Status</th>
              <th style={{ padding: 8 }}>Last synced</th>
            </tr>
          </thead>
          <tbody>
            {connections.map((connection) => (
              <tr key={connection.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: 8 }}>{connection.source}</td>
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
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
