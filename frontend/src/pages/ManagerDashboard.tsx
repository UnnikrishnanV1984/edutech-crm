import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getFunnel, getSlaCompliance, type FunnelRow, type SlaComplianceRow } from "../api/reports";
import { useAuth } from "../auth/context";
import { EmptyState } from "../components/EmptyState";

export function ManagerDashboard() {
  const { token } = useAuth();
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [compliance, setCompliance] = useState<SlaComplianceRow[]>([]);

  useEffect(() => {
    if (!token) return;
    getFunnel(token).then((response) => setFunnel(response.data));
    getSlaCompliance(token).then((response) => setCompliance(response.data));
  }, [token]);

  const maxCount = Math.max(1, ...funnel.map((f) => f.count));

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1>Team dashboard</h1>
        <div style={{ display: "flex", gap: 16, fontSize: 13 }}>
          <Link to="/escalations">Escalations →</Link>
          <Link to="/follow-ups">Follow-ups →</Link>
        </div>
      </div>

      <h2 style={{ fontSize: 16, marginTop: 24, marginBottom: 8 }}>Team funnel</h2>
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

      <h2 style={{ fontSize: 16, marginTop: 24, marginBottom: 8 }}>SLA compliance</h2>
      {compliance.length === 0 && <EmptyState headline="No SLA-tracked deals yet" />}
      {compliance.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: 8 }}>Counselor</th>
              <th style={{ padding: 8 }}>On track</th>
              <th style={{ padding: 8 }}>At risk</th>
              <th style={{ padding: 8 }}>Breached</th>
            </tr>
          </thead>
          <tbody>
            {compliance.map((row) => (
              <tr key={row.counselor_id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: 8 }}>{row.counselor_name ?? row.counselor_id}</td>
                <td style={{ padding: 8, color: "var(--success)" }}>{row.on_track}</td>
                <td style={{ padding: 8, color: "var(--warning)" }}>{row.at_risk}</td>
                <td style={{ padding: 8, color: "var(--danger)" }}>{row.breached}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
