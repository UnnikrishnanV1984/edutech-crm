import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  getFunnel,
  getInvoiceSummary,
  getSlaCompliance,
  getSourceAttribution,
  reportPeriodLabel,
} from "../api/reports";
import type {
  FunnelRow,
  InvoiceSummary,
  ReportPeriod,
  SlaComplianceRow,
  SourceAttributionRow,
} from "../api/reports";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner } from "../components/Spinner";
import { DashboardTopBar, MetricCard, MyQueueTodayCard, PipelineByStageCard } from "./DashboardWidgets";
import { useMe } from "../useMe";

export function AdminDashboard() {
  const { token } = useAuth();
  const { me } = useMe();
  const navigate = useNavigate();
  const [period, setPeriod] = useState<ReportPeriod>("last_30_days");
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [sources, setSources] = useState<SourceAttributionRow[]>([]);
  const [invoiceSummary, setInvoiceSummary] = useState<InvoiceSummary | undefined>(undefined);
  const [compliance, setCompliance] = useState<SlaComplianceRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!token) return;
    // Deliberate — re-shows the spinner on every period change, not just
    // the first load.
    // oxlint-disable-next-line react/set-state-in-effect
    setLoaded(false);
    getFunnel(token, period).then((response) => {
      setFunnel(response.data);
      setLoaded(true);
    });
    listPipelineStages(token).then((response) => setStages(response.data));
    getSourceAttribution(token, period).then((response) => setSources(response.data));
    getInvoiceSummary(token, period).then((response) => setInvoiceSummary(response.data));
    getSlaCompliance(token, period).then((response) => setCompliance(response.data));
  }, [token, period]);

  const pipelineValue = funnel.reduce((sum, row) => sum + Number(row.value), 0);
  const wonStageIds = new Set(stages.filter((s) => s.is_won).map((s) => s.id));
  const lostStageIds = new Set(stages.filter((s) => s.is_lost).map((s) => s.id));
  const totalDeals = funnel.reduce((sum, row) => sum + row.count, 0);
  const wonDeals = funnel
    .filter((row) => wonStageIds.has(row.stage_id))
    .reduce((sum, row) => sum + row.count, 0);
  const openDeals = funnel
    .filter((row) => !wonStageIds.has(row.stage_id) && !lostStageIds.has(row.stage_id))
    .reduce((sum, row) => sum + row.count, 0);
  const atRisk = compliance.reduce((sum, row) => sum + row.at_risk, 0);
  const breached = compliance.reduce((sum, row) => sum + row.breached, 0);
  const conversion = totalDeals > 0 ? Math.round((wonDeals / totalDeals) * 100) : 0;

  const quickLinks = (
    <div style={{ display: "flex", gap: "var(--space-2)" }}>
      <Button variant="secondary" onClick={() => navigate("/sla-policies")}>
        SLA policies
      </Button>
      <Button variant="secondary" onClick={() => navigate("/workflow-rules")}>
        Workflow rules
      </Button>
      <Button variant="secondary" onClick={() => navigate("/integrations")}>
        Integrations
      </Button>
    </div>
  );

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <DashboardTopBar roleLabel="Admin view" period={period} onPeriodChange={setPeriod}>
        {quickLinks}
      </DashboardTopBar>

      {!loaded && <PageSpinner />}

      {loaded && (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <div className="grid-4col">
          <MetricCard label="Open deals" value={openDeals} />
          <MetricCard label="SLA at risk" value={atRisk} accent />
          <MetricCard label="Breached" value={breached} />
          <MetricCard label="Conversion" value={`${conversion}%`} />
        </div>

        {invoiceSummary && (
          <div className="grid-4col">
            <Card title={`Invoiced (${reportPeriodLabel(period)})`}>
              <p style={{ fontSize: "var(--text-xl)", margin: 0 }}>
                {Number(invoiceSummary.invoiced_total).toLocaleString()}
              </p>
            </Card>
            <Card title={`Paid (${reportPeriodLabel(period)})`}>
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

        <div className="grid-split-14">
          <PipelineByStageCard funnel={funnel} stages={stages} />
          {token && me && <MyQueueTodayCard token={token} meId={me.user.id} />}
        </div>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: "var(--weight-semibold)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--text-muted)",
              }}
            >
              Team SLA
            </span>
            <div style={{ flex: 1 }} />
            <Button variant="text" onClick={() => navigate("/escalations")}>
              Open escalations
            </Button>
          </div>
          {compliance.length === 0 && (
            <div style={{ marginTop: "var(--space-4)" }}>
              <EmptyState headline="No SLA-tracked deals yet" />
            </div>
          )}
          {compliance.length > 0 && (
            <div className="table-scroll" style={{ marginTop: "var(--space-4)" }}>
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
            </div>
          )}
        </Card>

        <div className="grid-2col">
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
                        width: `${(row.count / Math.max(1, ...funnel.map((f) => f.count))) * 100}%`,
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

      </div>
      )}
    </div>
  );
}
