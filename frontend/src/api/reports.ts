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

export async function getFunnel(token: string): Promise<ReportEnvelope<FunnelRow[]>> {
  return apiGet<ReportEnvelope<FunnelRow[]>>(token, "/api/v1/reports/funnel");
}

export async function getSourceAttribution(
  token: string,
): Promise<ReportEnvelope<SourceAttributionRow[]>> {
  return apiGet<ReportEnvelope<SourceAttributionRow[]>>(
    token,
    "/api/v1/reports/source-attribution",
  );
}

export async function getForecast(token: string): Promise<ReportEnvelope<ForecastReport>> {
  return apiGet<ReportEnvelope<ForecastReport>>(token, "/api/v1/reports/forecast");
}

export async function getInvoiceSummary(token: string): Promise<ReportEnvelope<InvoiceSummary>> {
  return apiGet<ReportEnvelope<InvoiceSummary>>(token, "/api/v1/reports/invoices");
}

export async function getSlaCompliance(
  token: string,
): Promise<ReportEnvelope<SlaComplianceRow[]>> {
  return apiGet<ReportEnvelope<SlaComplianceRow[]>>(token, "/api/v1/reports/sla-compliance");
}

export async function getMyQueue(token: string): Promise<ReportEnvelope<MyQueueItem[]>> {
  return apiGet<ReportEnvelope<MyQueueItem[]>>(token, "/api/v1/reports/my-queue");
}

export async function getMyStats(token: string): Promise<ReportEnvelope<MyStats>> {
  return apiGet<ReportEnvelope<MyStats>>(token, "/api/v1/reports/my-stats");
}

// Re-exported so pages don't need to import DataEnvelope separately when
// they also fetch a plain (non-report) resource.
export type { DataEnvelope };
