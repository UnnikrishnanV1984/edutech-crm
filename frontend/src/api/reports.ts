import { apiGet } from "./client";
import type { DataEnvelope } from "./types";

interface ReportMeta {
  request_id: string;
  cached_at: string;
}

interface ReportEnvelope<T> {
  data: T;
  meta: ReportMeta;
}

export interface FunnelRow {
  stage_id: string;
  stage_name: string;
  count: number;
  value: string;
}

export interface SourceAttributionRow {
  lead_source: string;
  count: number;
}

export interface ForecastStageRow {
  stage_id: string;
  stage_name: string;
  deal_count: number;
  value: string;
  win_probability_pct: number;
  expected_count: number;
  expected_value: string;
}

export interface ForecastReport {
  expected_enrollments: number;
  expected_value: string;
  by_stage: ForecastStageRow[];
}

export interface InvoiceSummary {
  period: string;
  invoiced_total: string;
  paid_total: string;
  outstanding_total: string;
  invoice_rework_rate: number;
  avg_minutes_in_invoice_stage: number | null;
}

// The dashboard date-range picker's fixed token set — DashboardWidgets.tsx
// mirrors this exact list. Sent verbatim as the `period` query param;
// resolve_period on the backend falls back to "last_30_days" for
// anything it doesn't recognize.
export type ReportPeriod =
  | "last_30_days"
  | "last_60_days"
  | "this_quarter"
  | "last_quarter"
  | "this_year"
  | "last_year";

export const REPORT_PERIOD_OPTIONS: { value: ReportPeriod; label: string }[] = [
  { value: "last_30_days", label: "Last 30 days" },
  { value: "last_60_days", label: "Last 60 days" },
  { value: "this_quarter", label: "This Quarter" },
  { value: "last_quarter", label: "Last Quarter" },
  { value: "this_year", label: "This Year" },
  { value: "last_year", label: "Last Year" },
];

export function reportPeriodLabel(period: ReportPeriod): string {
  return REPORT_PERIOD_OPTIONS.find((option) => option.value === period)?.label ?? period;
}

export interface SlaComplianceRow {
  counselor_id: string;
  counselor_name: string | null;
  on_track: number;
  at_risk: number;
  breached: number;
}

export type SlaUrgency = "breached" | "at_risk" | "on_track" | null;

export interface MyQueueItem {
  deal_id: string;
  contact_id: string;
  stage_id: string;
  sla_state: SlaUrgency;
}

export interface MyStats {
  leads_worked: number;
  won_count: number;
  conversion_rate: number;
}

export interface EscalationSummary {
  open: number;
  breaching_within_1h: number;
  avg_resolve_minutes: number;
  reopened: number;
}

function periodQuery(period?: ReportPeriod): string {
  return period ? `?period=${period}` : "";
}

export async function getFunnel(
  token: string,
  period?: ReportPeriod,
): Promise<ReportEnvelope<FunnelRow[]>> {
  return apiGet<ReportEnvelope<FunnelRow[]>>(token, `/api/v1/reports/funnel${periodQuery(period)}`);
}

export async function getSourceAttribution(
  token: string,
  period?: ReportPeriod,
): Promise<ReportEnvelope<SourceAttributionRow[]>> {
  return apiGet<ReportEnvelope<SourceAttributionRow[]>>(
    token,
    `/api/v1/reports/source-attribution${periodQuery(period)}`,
  );
}

export async function getForecast(token: string): Promise<ReportEnvelope<ForecastReport>> {
  return apiGet<ReportEnvelope<ForecastReport>>(token, "/api/v1/reports/forecast");
}

export async function getInvoiceSummary(
  token: string,
  period?: ReportPeriod,
): Promise<ReportEnvelope<InvoiceSummary>> {
  return apiGet<ReportEnvelope<InvoiceSummary>>(
    token,
    `/api/v1/reports/invoices${periodQuery(period)}`,
  );
}

export async function getSlaCompliance(
  token: string,
  period?: ReportPeriod,
): Promise<ReportEnvelope<SlaComplianceRow[]>> {
  return apiGet<ReportEnvelope<SlaComplianceRow[]>>(
    token,
    `/api/v1/reports/sla-compliance${periodQuery(period)}`,
  );
}

export async function getMyQueue(token: string): Promise<ReportEnvelope<MyQueueItem[]>> {
  return apiGet<ReportEnvelope<MyQueueItem[]>>(token, "/api/v1/reports/my-queue");
}

export async function getMyStats(
  token: string,
  period?: ReportPeriod,
): Promise<ReportEnvelope<MyStats>> {
  return apiGet<ReportEnvelope<MyStats>>(token, `/api/v1/reports/my-stats${periodQuery(period)}`);
}

export async function getEscalationSummary(
  token: string,
): Promise<ReportEnvelope<EscalationSummary>> {
  return apiGet<ReportEnvelope<EscalationSummary>>(token, "/api/v1/reports/escalations");
}

// Re-exported so pages don't need to import DataEnvelope separately when
// they also fetch a plain (non-report) resource.
export type { DataEnvelope };
