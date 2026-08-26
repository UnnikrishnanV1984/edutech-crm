import { Fragment, useEffect, useState } from "react";

import { ApiRequestError } from "../api/client";
import { listCourses, type Course } from "../api/courses";
import { listDeals, type Deal } from "../api/deals";
import {
  createInvoice,
  listInvoicesForDeal,
  updateInvoice,
  type Invoice,
  type InvoiceStatus,
} from "../api/invoices";
import { createPayment, listPaymentsForInvoice, type Payment } from "../api/payments";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Spinner } from "../components/Spinner";
import { stageColor } from "../stageColor";
import { CreateDealPanel } from "./CreateDealPanel";

const INVOICE_STATUS_TONE: Record<InvoiceStatus, { bg: string; fg: string; border: string }> = {
  draft: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
  sent: { bg: "var(--accent-subtle)", fg: "var(--accent)", border: "transparent" },
  rework_requested: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  paid: { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" },
  cancelled: { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" },
};

const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Draft",
  sent: "Sent",
  rework_requested: "Rework requested",
  paid: "Paid",
  cancelled: "Cancelled",
};

function formatMoney(value: string, currency: string) {
  const amount = Number(value);
  return `${currency} ${Number.isFinite(amount) ? amount.toLocaleString() : value}`;
}

function dealStatusLabel(stage: PipelineStage | undefined): string {
  if (!stage) return "—";
  if (stage.is_invoice_stage) return "Invoice";
  if (stage.is_won) return "Won";
  if (stage.is_lost) return "Lost";
  return "Open";
}

interface DealsSectionProps {
  contactId: string;
}

export function DealsSection({ contactId }: DealsSectionProps) {
  const { token } = useAuth();
  const [deals, setDeals] = useState<Deal[] | undefined>(undefined);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [expandedDealId, setExpandedDealId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listDeals(token, { contact_id: contactId }).then((response) => setDeals(response.data));
    listPipelineStages(token).then((response) => setStages(response.data));
    listCourses(token).then((response) => setCourses(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, contactId]);

  function stageFor(stageId: string) {
    const index = stages.findIndex((s) => s.id === stageId);
    const stage = stages[index];
    return stage ? { stage, index } : undefined;
  }

  function courseName(courseId: string | null) {
    if (!courseId) return "General deal"; // non-EdTech deal, no course attached
    return courses.find((c) => c.id === courseId)?.name ?? "Unknown course";
  }

  return (
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
          Deals
        </span>
        {deals && <Badge label={String(deals.length).padStart(2, "0")} />}
        <div style={{ flex: 1 }} />
        <Button variant="secondary" onClick={() => setShowCreate(true)}>
          + New deal
        </Button>
      </div>
      {deals === undefined && (
        <div style={{ padding: 8, marginTop: "var(--space-3)" }}>
          <Spinner size={16} />
        </div>
      )}
      {deals && deals.length === 0 && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <EmptyState headline="No deals yet" />
        </div>
      )}
      {deals && deals.length > 0 && (
        <div className="table-scroll">
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "var(--space-3)" }}>
          <tbody>
            {deals.map((deal) => {
              const stageInfo = stageFor(deal.stage_id);
              const expanded = expandedDealId === deal.id;
              return (
                <Fragment key={deal.id}>
                  <tr
                    onClick={() => setExpandedDealId(expanded ? undefined : deal.id)}
                    style={{ borderBottom: expanded ? "none" : "1px solid var(--border)", cursor: "pointer" }}
                  >
                    <td style={{ padding: "var(--space-2)" }}>{courseName(deal.course_id)}</td>
                    <td style={{ padding: "var(--space-2)" }}>
                      {stageInfo && (
                        <Badge label={stageInfo.stage.name} tone={stageColor(stageInfo.stage, stageInfo.index)} />
                      )}
                    </td>
                    <td style={{ padding: "var(--space-2)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
                      {Number(deal.value) > 0 ? formatMoney(deal.value, deal.currency) : ""}
                    </td>
                    <td style={{ padding: "var(--space-2)", textAlign: "right" }}>
                      <Badge label={dealStatusLabel(stageInfo?.stage)} />
                    </td>
                  </tr>
                  {expanded && (
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <td colSpan={4} style={{ padding: 0 }}>
                        <DealInvoices deal={deal} stage={stageInfo?.stage} onDealChanged={load} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        </div>
      )}
      {showCreate && (
        <CreateDealPanel
          contactId={contactId}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </Card>
  );
}

function DealInvoices({
  deal,
  stage,
  onDealChanged,
}: {
  deal: Deal;
  stage: PipelineStage | undefined;
  onDealChanged: () => void;
}) {
  const { token } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [showCreateInvoice, setShowCreateInvoice] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listInvoicesForDeal(token, deal.id).then((response) => {
      setInvoices(response.data);
      setLoaded(true);
    });
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token, deal.id]);

  const openInvoice = invoices.find((invoice) => invoice.status !== "cancelled");
  const canCreateInvoice = stage?.is_invoice_stage && !openInvoice;

  return (
    <div
      style={{
        padding: "var(--space-3) var(--space-4)",
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
      }}
    >
      {error && (
        <p role="alert" style={{ color: "var(--danger)", margin: 0 }}>
          {error}
        </p>
      )}

      {canCreateInvoice && !showCreateInvoice && (
        <Button variant="primary" onClick={() => setShowCreateInvoice(true)}>
          Create invoice
        </Button>
      )}

      {showCreateInvoice && (
        <CreateInvoiceForm
          dealId={deal.id}
          onCreated={() => {
            setShowCreateInvoice(false);
            load();
          }}
          onCancel={() => setShowCreateInvoice(false)}
        />
      )}

      {loaded && invoices.length === 0 && !canCreateInvoice && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", margin: 0 }}>
          No invoices yet.
        </p>
      )}

      {invoices.map((invoice) => (
        <InvoiceRow
          key={invoice.id}
          invoice={invoice}
          currency={deal.currency}
          onChanged={() => {
            load();
            onDealChanged();
          }}
          onError={setError}
        />
      ))}
    </div>
  );
}

function CreateInvoiceForm({
  dealId,
  onCreated,
  onCancel,
}: {
  dealId: string;
  onCreated: () => void;
  onCancel: () => void;
}) {
  const { token } = useAuth();
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      await createInvoice(token, dealId, { invoice_number: invoiceNumber, amount });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't create invoice");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        void handleSubmit(event);
      }}
      style={{
        display: "flex",
        gap: "var(--space-2)",
        alignItems: "flex-end",
        flexWrap: "wrap",
      }}
    >
      <label>
        Invoice number*
        <input
          required
          value={invoiceNumber}
          onChange={(event) => setInvoiceNumber(event.target.value)}
          style={{ display: "block", marginTop: 4 }}
        />
      </label>
      <label>
        Amount*
        <input
          required
          type="number"
          min="0"
          step="0.01"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          style={{ display: "block", marginTop: 4, width: 140 }}
        />
      </label>
      <Button variant="primary" type="submit" disabled={submitting}>
        {submitting ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Spinner size={12} /> Creating…
          </span>
        ) : (
          "Create"
        )}
      </Button>
      <Button variant="text" onClick={onCancel} disabled={submitting}>
        Cancel
      </Button>
      {error && (
        <p role="alert" style={{ color: "var(--danger)", width: "100%", margin: 0 }}>
          {error}
        </p>
      )}
    </form>
  );
}

function InvoiceRow({
  invoice,
  currency,
  onChanged,
  onError,
}: {
  invoice: Invoice;
  currency: string;
  onChanged: () => void;
  onError: (message: string | undefined) => void;
}) {
  const { token } = useAuth();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [showPayments, setShowPayments] = useState(false);
  const [busy, setBusy] = useState(false);

  function loadPayments() {
    if (!token) return;
    listPaymentsForInvoice(token, invoice.id).then((response) => setPayments(response.data));
  }

  async function transition(status: "sent" | "cancelled") {
    if (!token) return;
    setBusy(true);
    onError(undefined);
    try {
      await updateInvoice(token, invoice.id, { status });
      onChanged();
    } catch (err) {
      onError(err instanceof ApiRequestError ? err.message : "Couldn't update invoice");
    } finally {
      setBusy(false);
    }
  }

  const paidTotal = payments.reduce((sum, payment) => sum + Number(payment.amount), 0);
  const outstanding = Number(invoice.amount) - paidTotal;
  const canRecordPayment = invoice.status === "sent" || invoice.status === "rework_requested";
  const canSend = invoice.status === "draft" || invoice.status === "rework_requested";
  const canCancel = invoice.status !== "paid" && invoice.status !== "cancelled";

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "var(--space-3)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <span style={{ fontWeight: "var(--weight-semibold)" }}>{invoice.invoice_number}</span>
          <Badge
            label={INVOICE_STATUS_LABELS[invoice.status]}
            tone={INVOICE_STATUS_TONE[invoice.status]}
          />
          {invoice.was_reworked && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
              Reworked
            </span>
          )}
        </div>
        <span style={{ fontSize: "var(--text-sm)" }}>{formatMoney(invoice.amount, currency)}</span>
      </div>

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        {canSend && (
          <Button variant="secondary" disabled={busy} onClick={() => void transition("sent")}>
            Send
          </Button>
        )}
        {canCancel && (
          <Button variant="text" disabled={busy} onClick={() => void transition("cancelled")}>
            Cancel
          </Button>
        )}
        {(invoice.status === "sent" ||
          invoice.status === "rework_requested" ||
          invoice.status === "paid") && (
          <Button
            variant="text"
            onClick={() => {
              setShowPayments((v) => !v);
              if (!showPayments) loadPayments();
            }}
          >
            {showPayments ? "Hide payments" : "Payments"}
          </Button>
        )}
      </div>

      {showPayments && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {payments.length === 0 && (
            <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", margin: 0 }}>
              No payments recorded yet.
            </p>
          )}
          {payments.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {payments.map((payment) => (
                <li
                  key={payment.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "var(--text-sm)",
                    padding: "2px 0",
                  }}
                >
                  <span>
                    {formatMoney(payment.amount, currency)} {payment.method && `(${payment.method})`}
                  </span>
                  <span style={{ color: "var(--text-muted)" }}>
                    {new Date(payment.paid_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p style={{ fontSize: "var(--text-sm)", margin: 0 }}>
            Outstanding: {formatMoney(outstanding.toFixed(2), currency)}
          </p>
          {canRecordPayment && (
            <RecordPaymentForm
              invoiceId={invoice.id}
              onRecorded={() => {
                loadPayments();
                onChanged();
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}

function RecordPaymentForm({
  invoiceId,
  onRecorded,
}: {
  invoiceId: string;
  onRecorded: () => void;
}) {
  const { token } = useAuth();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      await createPayment(token, invoiceId, { amount, method: method || undefined });
      setAmount("");
      setMethod("");
      onRecorded();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't record payment");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        void handleSubmit(event);
      }}
      style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}
    >
      <input
        required
        type="number"
        min="0"
        step="0.01"
        placeholder="Amount"
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
        style={{ width: 100 }}
      />
      <input
        placeholder="Method (optional)"
        value={method}
        onChange={(event) => setMethod(event.target.value)}
        style={{ width: 140 }}
      />
      <Button variant="secondary" type="submit" disabled={submitting}>
        {submitting ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Spinner size={12} /> Recording…
          </span>
        ) : (
          "Record payment"
        )}
      </Button>
      {error && (
        <p role="alert" style={{ color: "var(--danger)", width: "100%", margin: 0 }}>
          {error}
        </p>
      )}
    </form>
  );
}
