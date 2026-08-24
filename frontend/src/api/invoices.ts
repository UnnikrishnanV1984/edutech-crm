import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type InvoiceStatus = "draft" | "sent" | "rework_requested" | "paid" | "cancelled";

export interface Invoice {
  id: string;
  deal_id: string;
  invoice_number: string;
  amount: string;
  status: InvoiceStatus;
  was_reworked: boolean;
  issued_at: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export async function listInvoicesForDeal(
  token: string,
  dealId: string,
): Promise<DataEnvelope<Invoice[]>> {
  return apiGet<DataEnvelope<Invoice[]>>(token, `/api/v1/deals/${dealId}/invoices`);
}

export async function createInvoice(
  token: string,
  dealId: string,
  input: { invoice_number: string; amount: string; due_date?: string },
): Promise<DataEnvelope<Invoice>> {
  return apiPost<DataEnvelope<Invoice>>(token, `/api/v1/deals/${dealId}/invoices`, input);
}

// status here is intentionally narrower than InvoiceStatus — rework_requested
// and paid are system-only (app/services/invoice_service.py), never client-settable.
export async function updateInvoice(
  token: string,
  invoiceId: string,
  input: { amount?: string; due_date?: string; status?: "sent" | "cancelled" },
): Promise<DataEnvelope<Invoice>> {
  return apiPatch<DataEnvelope<Invoice>>(token, `/api/v1/invoices/${invoiceId}`, input);
}
