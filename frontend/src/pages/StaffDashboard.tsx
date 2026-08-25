import { useEffect, useState } from "react";

import { getFunnel, getMyQueue, getMyStats, type FunnelRow, type MyQueueItem, type MyStats } from "../api/reports";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { DashboardTopBar, MetricCard, MyQueueTodayCard, PipelineByStageCard } from "./DashboardWidgets";
import { useMe } from "../useMe";

export function StaffDashboard() {
  const { token } = useAuth();
  const { me } = useMe();
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [queue, setQueue] = useState<MyQueueItem[]>([]);
  const [stats, setStats] = useState<MyStats | undefined>(undefined);

  useEffect(() => {
    if (!token || !me) return;
    getFunnel(token).then((response) => setFunnel(response.data));
    listPipelineStages(token).then((response) => setStages(response.data));
    getMyQueue(token).then((response) => setQueue(response.data));
    getMyStats(token).then((response) => setStats(response.data));
  }, [token, me]);

  const atRisk = queue.filter((item) => item.sla_state === "at_risk").length;
  const breached = queue.filter((item) => item.sla_state === "breached").length;

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <DashboardTopBar roleLabel="My view" />

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <div style={{ display: "flex", gap: "var(--space-4)" }}>
          <MetricCard label="Open deals" value={queue.length} />
          <MetricCard label="SLA at risk" value={atRisk} accent />
          <MetricCard label="Breached" value={breached} />
          <MetricCard
            label="Conversion"
            value={stats ? `${Math.round(stats.conversion_rate * 100)}%` : "—"}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "var(--space-5)" }}>
          <PipelineByStageCard funnel={funnel} stages={stages} />
          {token && me && <MyQueueTodayCard token={token} meId={me.user.id} />}
        </div>
      </div>
    </div>
  );
}
