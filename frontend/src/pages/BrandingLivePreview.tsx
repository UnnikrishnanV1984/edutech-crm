import { useState } from "react";

import type { BrandingDraft } from "../api/branding";
import { HEADER_BACKGROUND_COLORS } from "../branding/colorUtils";
import { Card } from "../components/Card";

type PreviewTab = "app" | "login" | "email";

const TABS: { value: PreviewTab; label: string }[] = [
  { value: "app", label: "App" },
  { value: "login", label: "Login" },
  { value: "email", label: "Email" },
];

function Chip({ label, selected }: { label: string; selected: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-medium)",
        padding: "3px 8px",
        borderRadius: 999,
        border: `1px solid ${selected ? "var(--text-h)" : "var(--border)"}`,
        color: selected ? "var(--text-h)" : "var(--text-muted)",
      }}
    >
      {label}
    </span>
  );
}

function resolveHeaderBg(draft: BrandingDraft): string {
  if (draft.header_background === "accent") return draft.accent_color ?? "#ffffff";
  return HEADER_BACKGROUND_COLORS[draft.header_background] ?? "#ffffff";
}

// Renders a small, honest mockup of this app's own real component style
// (accent-outlined primary button, per Button.tsx — never a filled
// block) using the draft's current values, not the wireframe's own
// filled-button convention, so this preview matches what the admin will
// actually see once published.
function AppPreview({ draft }: { draft: BrandingDraft }) {
  const accent = draft.accent_color ?? "#b68235";
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          padding: "9px 11px",
          borderBottom: "1px solid var(--border)",
          background: resolveHeaderBg(draft),
        }}
      >
        {draft.logo_url && (
          <img src={draft.logo_url} alt="" style={{ width: 18, height: 18, borderRadius: 4 }} />
        )}
        <span style={{ fontSize: 11, fontWeight: "var(--weight-medium)" }}>
          {draft.company_display_name ?? "OpenFunnel"}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "56px 1fr", minHeight: 110 }}>
        <div
          style={{
            borderRight: "1px solid var(--border)",
            padding: "7px 6px",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div style={{ height: 6, background: "var(--border)" }} />
          <div style={{ height: 6, background: accent, width: "80%" }} />
          <div style={{ height: 6, background: "var(--border)", width: "70%" }} />
        </div>
        <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ height: 6, background: "var(--border)", width: "56%" }} />
          <button
            type="button"
            disabled
            style={{
              alignSelf: "flex-start",
              fontSize: 9,
              fontWeight: "var(--weight-medium)",
              padding: "5px 9px",
              background: "transparent",
              color: accent,
              border: `1px solid ${accent}`,
              borderRadius: "var(--radius-sm)",
            }}
          >
            PRIMARY
          </button>
        </div>
      </div>
    </div>
  );
}

function PreviewOnlyNote() {
  return (
    <p style={{ fontSize: "var(--text-xs)", color: "var(--danger)", margin: "8px 0 0" }}>
      Preview only — not yet live. This app has no in-app login page or
      outbound email sending, so nothing renders this for real yet.
    </p>
  );
}

function LoginPreview({ draft }: { draft: BrandingDraft }) {
  const accent = draft.accent_color ?? "#b68235";
  return (
    <div>
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-sm)",
          padding: 16,
          textAlign: "center",
          backgroundImage: draft.login_backdrop_url ? `url(${draft.login_backdrop_url})` : undefined,
          backgroundSize: "cover",
        }}
      >
        {draft.logo_url && (
          <img src={draft.logo_url} alt="" style={{ width: 28, height: 28, borderRadius: 6 }} />
        )}
        <div style={{ fontSize: 12, fontWeight: "var(--weight-medium)", marginTop: 6 }}>
          {draft.company_display_name ?? "OpenFunnel"}
        </div>
        <button
          type="button"
          disabled
          style={{
            marginTop: 10,
            fontSize: 9,
            padding: "5px 9px",
            background: "transparent",
            color: accent,
            border: `1px solid ${accent}`,
            borderRadius: "var(--radius-sm)",
          }}
        >
          Sign in
        </button>
      </div>
      <PreviewOnlyNote />
    </div>
  );
}

function EmailPreview({ draft }: { draft: BrandingDraft }) {
  return (
    <div>
      <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}>
        <div
          style={{
            padding: "9px 11px",
            borderBottom: "1px solid var(--border)",
            background: resolveHeaderBg(draft),
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {draft.logo_url && (
            <img src={draft.logo_url} alt="" style={{ width: 16, height: 16, borderRadius: 3 }} />
          )}
          <span style={{ fontSize: 11 }}>{draft.company_display_name ?? "OpenFunnel"}</span>
        </div>
        <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ height: 6, background: "var(--border)", width: "80%" }} />
          <div style={{ height: 6, background: "var(--border)", width: "64%" }} />
        </div>
      </div>
      <PreviewOnlyNote />
    </div>
  );
}

interface AppearanceRow {
  label: string;
  status: "live" | "preview" | "unavailable";
}

const APPEARANCE_ROWS: AppearanceRow[] = [
  { label: "App sidebar & header", status: "live" },
  { label: "Login screen", status: "preview" },
  { label: "Outbound emails", status: "preview" },
  { label: "Invoices & PDFs", status: "unavailable" },
];

const STATUS_LABEL: Record<AppearanceRow["status"], string> = {
  live: "Live",
  preview: "Preview only",
  unavailable: "Not available yet",
};

export function BrandingLivePreview({ draft }: { draft: BrandingDraft }) {
  const [tab, setTab] = useState<PreviewTab>("app");

  return (
    <>
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Live preview</span>
          <div style={{ flex: 1 }} />
          {TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTab(t.value)}
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer" }}
            >
              <Chip label={t.label} selected={tab === t.value} />
            </button>
          ))}
        </div>
        <div style={{ marginTop: 12 }}>
          {tab === "app" && <AppPreview draft={draft} />}
          {tab === "login" && <LoginPreview draft={draft} />}
          {tab === "email" && <EmailPreview draft={draft} />}
        </div>
      </Card>

      <Card title="Where branding appears">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {APPEARANCE_ROWS.map((row) => (
            <div
              key={row.label}
              style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)" }}
            >
              <span>{row.label}</span>
              <span
                style={{
                  color: row.status === "live" ? "var(--success)" : "var(--text-muted)",
                  fontSize: "var(--text-xs)",
                }}
              >
                {STATUS_LABEL[row.status]}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}
