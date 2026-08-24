import { apiGet, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export interface Payment {
  id: string;
  invoice_id: string;
  amount: string;
  paid_at: string;
  method: string | null;
  created_at: string;
}

export async function listPaymentsForInvoice(
  token: string,
  invoiceId: string,
): Promise<DataEnvelope<Payment[]>> {
  return apiGet<DataEnvelope<Payment[]>>(token, `/api/v1/invoices/${invoiceId}/payments`);
}

export async function createPayment(
  token: string,
  invoiceId: string,
  input: { amount: string; method?: string },
): Promise<DataEnvelope<Payment>> {
  return apiPost<DataEnvelope<Payment>>(token, `/api/v1/invoices/${invoiceId}/payments`, input);
}
