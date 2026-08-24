import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listConnections, type LeadSourceConnection } from "../api/leadSourceConnections";
import { getForecast, getFunnel, getInvoiceSummary, getSourceAttribution } from "../api/reports";
import type {
  ForecastReport,
  FunnelRow,
  InvoiceSummary,
  SourceAttributionRow,
} from "../api/reports";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";

export function AdminDashboard() {
  const { token } = useAuth();
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [sources, setSources] = useState<SourceAttributionRow[]>([]);
  const [forecast, setForecast] = useState<ForecastReport | undefined>(undefined);
  const [invoiceSummary, setInvoiceSummary] = useState<InvoiceSummary | undefined>(undefined);
  const [connections, setConnections] = useState<LeadSourceConnection[]>([]);

  useEffect(() => {
    if (!token) return;
    getFunnel(token).then((response) => setFunnel(response.data));
    getSourceAttribution(token).then((response) => setSources(response.data));
    getForecast(token).then((response) => setForecast(response.data));
    getInvoiceSummary(token).then((response) => setInvoiceSummary(response.data));
    listConnections(token).then((response) => setConnections(response.data));
  }, [token]);

  const maxCount = Math.max(1, ...funnel.map((f) => f.count));
  const pipelineValue = funnel.reduce((sum, row) => sum + Number(row.value), 0);

  const quickLinks = (
    <div style={{ display: "flex", gap: "var(--space-4)", fontSize: "var(--text-sm)" }}>
      <Link to="/sla-policies">SLA policies →</Link>
      <Link to="/workflow-rules">Workflow rules →</Link>
      <Link to="/integrations">Integrations →</Link>
    </div>
  );

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: "var(--space-5)",
        }}
      >
        <h1 style={{ margin: 0 }}>Admin dashboard</h1>
        {quickLinks}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)" }}>
          <Card title={`Org funnel${pipelineValue > 0 ? ` — ${pipelineValue.toLocaleString()} pipeline value` : ""}`}>
            {funnel.length === 0 && <EmptyState headline="No deals yet" />}
            {funnel.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {funnel.map((row) => (
                  <div
                    key={row.stage_id}
                    style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}
                  >
                    <span style={{ width: 140, fontSize: "var(--text-sm)" }}>{row.stage_name}</span>
                    <div
                      style={{
                        height: 14,
                        borderRadius: "var(--radius-sm)",
                        background: "var(--accent-subtle)",
                        width: `${(row.count / maxCount) * 100}%`,
                        minWidth: row.count > 0 ? 4 : 0,
                      }}
                    />
                    <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
                      {row.count}
                      {Number(row.value) > 0 && ` · ${Number(row.value).toLocaleString()}`}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Leads by source">
            {sources.length === 0 && <EmptyState headline="No leads yet" />}
            {sources.length > 0 && (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {sources.map((row) => (
                  <li
                    key={row.lead_source}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "var(--space-1) 0",
                      fontSize: "var(--text-base)",
                    }}
                  >
                    <span>{row.lead_source}</span>
                    <span style={{ color: "var(--text-muted)" }}>{row.count}</span>
                  </li>
                ))}
              </ul>
            )}
            <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: 0 }}>
              Lead counts only — cost-per-enrollment needs ad-spend tracking this
              build doesn't have yet.
            </p>
          </Card>
        </div>

        {forecast && (
          <Card title={`Forecast — ${forecast.expected_enrollments} expected enrollments`}>
            <p style={{ fontSize: "var(--text-base)", margin: "0 0 var(--space-2)" }}>
              Weighted forecast value: {Number(forecast.expected_value).toLocaleString()}
            </p>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: 0 }}>
              Both figures are weighted by each stage's win probability — set
              those per stage to refine this.
            </p>
          </Card>
        )}

        {invoiceSummary && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-5)" }}>
            <Card title="Invoiced this month">
              <p style={{ fontSize: "var(--text-xl)", margin: 0 }}>
                {Number(invoiceSummary.invoiced_total).toLocaleString()}
              </p>
            </Card>
            <Card title="Paid this month">
              <p style={{ fontSize: "var(--text-xl)", margin: 0, color: "var(--success)" }}>
                {Number(invoiceSummary.paid_total).toLocaleString()}
              </p>
            </Card>
            <Card title="Outstanding">
              <p style={{ fontSize: "var(--text-xl)", margin: 0, color: "var(--warning)" }}>
                {Number(invoiceSummary.outstanding_total).toLocaleString()}
              </p>
            </Card>
            <Card title="Invoice rework rate">
              <p style={{ fontSize: "var(--text-xl)", margin: 0 }}>
                {Math.round(invoiceSummary.invoice_rework_rate * 100)}%
              </p>
              {invoiceSummary.avg_minutes_in_invoice_stage !== null && (
                <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: 0 }}>
                  Avg {Math.round(invoiceSummary.avg_minutes_in_invoice_stage)} min in an invoice
                  stage right now
                </p>
              )}
            </Card>
          </div>
        )}

        <Card title="Integration health">
          {connections.length === 0 && <EmptyState headline="No sources connected" />}
          {connections.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                  <th style={{ padding: "var(--space-2)" }}>Source</th>
                  <th style={{ padding: "var(--space-2)" }}>Status</th>
                  <th style={{ padding: "var(--space-2)" }}>Last synced</th>
                </tr>
              </thead>
              <tbody>
                {connections.map((connection) => (
                  <tr key={connection.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "var(--space-2)" }}>{connection.source}</td>
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
                    <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
                      {connection.last_synced_at
                        ? new Date(connection.last_synced_at).toLocaleString()
                        : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
