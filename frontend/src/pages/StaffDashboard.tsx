import { useEffect, useState } from "react";

import {
  getFunnel,
  getMyQueue,
  getMyStats,
  type FunnelRow,
  type MyQueueItem,
  type MyStats,
  type ReportPeriod,
} from "../api/reports";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { PageSpinner } from "../components/Spinner";
import { DashboardTopBar, MetricCard, MyQueueTodayCard, PipelineByStageCard } from "./DashboardWidgets";
import { useMe } from "../useMe";

export function StaffDashboard() {
  const { token } = useAuth();
  const { me } = useMe();
  const [period, setPeriod] = useState<ReportPeriod>("last_30_days");
  const [funnel, setFunnel] = useState<FunnelRow[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [queue, setQueue] = useState<MyQueueItem[]>([]);
  const [stats, setStats] = useState<MyStats | undefined>(undefined);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!token || !me) return;
    // Deliberate — re-shows the spinner on every period change, not just
    // the first load.
    // oxlint-disable-next-line react/set-state-in-effect
    setLoaded(false);
    getFunnel(token, period).then((response) => {
      setFunnel(response.data);
      setLoaded(true);
    });
    listPipelineStages(token).then((response) => setStages(response.data));
    getMyQueue(token).then((response) => setQueue(response.data));
    getMyStats(token, period).then((response) => setStats(response.data));
  }, [token, me, period]);

  // SLA at-risk/breached come from my-queue, a live "right now" snapshot
  // with no period dimension (unlike funnel/sla-compliance) — the two
  // counts below don't move with the date-range picker, by design.
  const wonStageIds = new Set(stages.filter((s) => s.is_won).map((s) => s.id));
  const lostStageIds = new Set(stages.filter((s) => s.is_lost).map((s) => s.id));
  const openDeals = funnel
    .filter((row) => !wonStageIds.has(row.stage_id) && !lostStageIds.has(row.stage_id))
    .reduce((sum, row) => sum + row.count, 0);
  const atRisk = queue.filter((item) => item.sla_state === "at_risk").length;
  const breached = queue.filter((item) => item.sla_state === "breached").length;

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <DashboardTopBar roleLabel="My view" period={period} onPeriodChange={setPeriod} />

      {!loaded && <PageSpinner />}

      {loaded && (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <div className="grid-4col">
          <MetricCard label="Open deals" value={openDeals} bar={1} />
          <MetricCard label="SLA at risk" value={atRisk} accent bar={3} />
          <MetricCard label="Breached" value={breached} bar={4} />
          <MetricCard
            label="Conversion"
            bar={2}
            value={stats ? `${Math.round(stats.conversion_rate * 100)}%` : "—"}
          />
        </div>

        <div className="grid-split-14">
          <PipelineByStageCard funnel={funnel} stages={stages} />
          {token && me && <MyQueueTodayCard token={token} meId={me.user.id} />}
        </div>
      </div>
      )}
    </div>
  );
}
