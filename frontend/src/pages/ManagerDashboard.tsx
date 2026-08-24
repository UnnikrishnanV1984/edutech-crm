import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  getFunnel,
  getInvoiceSummary,
  getSlaCompliance,
  type FunnelRow,
  type InvoiceSummary,
  type SlaComplianceRow,
} from "../api/reports";
import { useAuth } from "../auth/context";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";

export function ManagerDashboard() {
  const { token } = useAuth();
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [compliance, setCompliance] = useState<SlaComplianceRow[]>([]);
  const [invoiceSummary, setInvoiceSummary] = useState<InvoiceSummary | undefined>(undefined);

  useEffect(() => {
    if (!token) return;
    getFunnel(token).then((response) => setFunnel(response.data));
    getSlaCompliance(token).then((response) => setCompliance(response.data));
    getInvoiceSummary(token).then((response) => setInvoiceSummary(response.data));
  }, [token]);

  const maxCount = Math.max(1, ...funnel.map((f) => f.count));
  const pipelineValue = funnel.reduce((sum, row) => sum + Number(row.value), 0);

  const quickLinks = (
    <div style={{ display: "flex", gap: "var(--space-4)", fontSize: "var(--text-sm)" }}>
      <Link to="/escalations">Escalations →</Link>
      <Link to="/follow-ups">Follow-ups →</Link>
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
        <h1 style={{ margin: 0 }}>Team dashboard</h1>
        {quickLinks}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <Card title={`Team funnel${pipelineValue > 0 ? ` — ${pipelineValue.toLocaleString()} pipeline value` : ""}`}>
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

        <Card title="SLA compliance">
          {compliance.length === 0 && <EmptyState headline="No SLA-tracked deals yet" />}
          {compliance.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                  <th style={{ padding: "var(--space-2)" }}>Counselor</th>
                  <th style={{ padding: "var(--space-2)" }}>On track</th>
                  <th style={{ padding: "var(--space-2)" }}>At risk</th>
                  <th style={{ padding: "var(--space-2)" }}>Breached</th>
                </tr>
              </thead>
              <tbody>
                {compliance.map((row) => (
                  <tr key={row.counselor_id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "var(--space-2)" }}>
                      {row.counselor_name ?? row.counselor_id}
                    </td>
                    <td style={{ padding: "var(--space-2)", color: "var(--success)" }}>
                      {row.on_track}
                    </td>
                    <td style={{ padding: "var(--space-2)", color: "var(--warning)" }}>
                      {row.at_risk}
                    </td>
                    <td style={{ padding: "var(--space-2)", color: "var(--danger)" }}>
                      {row.breached}
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
