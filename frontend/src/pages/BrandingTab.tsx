import { useEffect, useRef, useState } from "react";

import {
  confirmBrandingAsset,
  discardBrandingDraft,
  getBrandingDraft,
  listBrandingVersions,
  publishBranding,
  requestBrandingUploadUrl,
  updateBrandingDraft,
  type BrandingAssetType,
  type BrandingDraft,
  type BrandingVersion,
  type HeaderBackground,
  type Typeface,
} from "../api/branding";
import { ApiRequestError } from "../api/client";
import { uploadFileToS3 } from "../api/documents";
import { useAuth } from "../auth/context";
import { contrastRatio, WCAG_AA_CONTRAST, HEADER_BACKGROUND_COLORS } from "../branding/colorUtils";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { PageSpinner, Spinner } from "../components/Spinner";
import { BrandingLivePreview } from "./BrandingLivePreview";
import { BrandingVersionHistory } from "./BrandingVersionHistory";

const ACCENT_PRESETS = ["#b68235", "#201f1d", "#6b6a67"];

const HEADER_BACKGROUND_OPTIONS: { value: HeaderBackground; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "accent", label: "Accent" },
];

const TYPEFACE_OPTIONS: { value: Typeface; label: string }[] = [
  { value: "system", label: "System" },
  { value: "serif", label: "Serif (Cormorant Garamond / Lora)" },
];

interface UploadWellProps {
  assetType: BrandingAssetType;
  label: string;
  helperText: string;
  currentUrl: string | null | undefined;
  onUploaded: () => void;
  compact?: boolean;
}

function UploadWell({
  assetType,
  label,
  helperText,
  currentUrl,
  onUploaded,
  compact,
}: UploadWellProps) {
  const { token } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleFile(file: File | null) {
    if (!file || !token) return;
    setUploading(true);
    setProgress(0);
    setError(undefined);
    try {
      const { data: upload } = await requestBrandingUploadUrl(token, {
        asset_type: assetType,
        filename: file.name,
        content_type: file.type || "image/png",
      });
      await uploadFileToS3(upload.upload_url, file, setProgress);
      await confirmBrandingAsset(token, { asset_type: assetType, s3_key: upload.s3_key });
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't upload this image");
    } finally {
      setUploading(false);
    }
  }

  if (compact) {
    return (
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{label}</div>
        <div style={{ display: "flex", gap: 8, marginTop: 7, alignItems: "center" }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "var(--radius-sm)",
              border: "1px dashed var(--border)",
              backgroundImage: currentUrl ? `url(${currentUrl})` : undefined,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          />
          <button
            type="button"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: "var(--weight-medium)",
              padding: "3px 10px",
              borderRadius: 999,
              border: "1px solid var(--text-h)",
              background: "transparent",
              color: "var(--text-h)",
              cursor: "pointer",
            }}
          >
            {uploading ? `${progress}%` : "Upload"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
          />
        </div>
        {error && (
          <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-xs)", margin: "4px 0 0" }}>
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{label}</div>
      <div
        style={{
          marginTop: 8,
          border: "2px dashed var(--border)",
          borderRadius: "var(--radius-sm)",
          minHeight: 118,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          padding: 12,
          background: "var(--surface)",
        }}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void handleFile(event.dataTransfer.files[0] ?? null);
        }}
      >
        {currentUrl && (
          <img
            src={currentUrl}
            alt={label}
            style={{ maxHeight: 56, maxWidth: "100%", objectFit: "contain" }}
          />
        )}
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{helperText}</span>
        {uploading ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Spinner size={12} /> Uploading… {progress}%
          </span>
        ) : (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: "var(--weight-medium)",
              padding: "3px 10px",
              borderRadius: 999,
              border: "1px solid var(--text-h)",
              background: "transparent",
              color: "var(--text-h)",
              cursor: "pointer",
            }}
          >
            Browse…
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
        />
      </div>
      {error && (
        <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-xs)", margin: "6px 0 0" }}>
          {error}
        </p>
      )}
    </div>
  );
}

export function BrandingTab() {
  const { token } = useAuth();
  const [draft, setDraft] = useState<BrandingDraft | undefined>(undefined);
  const [versions, setVersions] = useState<BrandingVersion[] | undefined>(undefined);
  const customColorInputRef = useRef<HTMLInputElement>(null);
  const [publishing, setPublishing] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [actionError, setActionError] = useState<string | undefined>(undefined);

  function loadDraft() {
    if (!token) return;
    getBrandingDraft(token).then((response) => setDraft(response.data));
  }

  function loadVersions() {
    if (!token) return;
    listBrandingVersions(token).then((response) => setVersions(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadDraft, [token]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadVersions, [token]);

  async function saveDraftFields(
    updates: Partial<{
      company_display_name: string | null;
      accent_color: string | null;
      header_background: HeaderBackground;
      typeface: Typeface;
      custom_domain: string | null;
    }>,
  ) {
    if (!token) return;
    const response = await updateBrandingDraft(token, updates);
    setDraft(response.data);
  }

  async function handlePublish() {
    if (!token) return;
    setPublishing(true);
    setActionError(undefined);
    try {
      await publishBranding(token);
      loadVersions();
    } catch (err) {
      setActionError(err instanceof ApiRequestError ? err.message : "Couldn't publish");
    } finally {
      setPublishing(false);
    }
  }

  async function handleDiscard() {
    if (!token) return;
    setDiscarding(true);
    setActionError(undefined);
    try {
      const response = await discardBrandingDraft(token);
      setDraft(response.data);
    } catch (err) {
      setActionError(err instanceof ApiRequestError ? err.message : "Couldn't discard");
    } finally {
      setDiscarding(false);
    }
  }

  async function handleRestored() {
    loadDraft();
    loadVersions();
  }

  if (!draft) return <PageSpinner />;

  const headerBgColor =
    draft.header_background === "accent"
      ? (draft.accent_color ?? "#ffffff")
      : (HEADER_BACKGROUND_COLORS[draft.header_background] ?? "#ffffff");
  const ratio = draft.accent_color ? contrastRatio(draft.accent_color, headerBgColor) : undefined;

  return (
    <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Button variant="secondary" disabled={discarding} onClick={() => void handleDiscard()}>
            {discarding ? "Discarding…" : "Discard"}
          </Button>
          <Button variant="primary" disabled={publishing} onClick={() => void handlePublish()}>
            {publishing ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> Publishing…
              </span>
            ) : (
              "Publish branding"
            )}
          </Button>
        </div>
        {actionError && (
          <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)", margin: 0 }}>
            {actionError}
          </p>
        )}

        <Card title="Company identity">
          <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginTop: -8 }}>
            Changes save to the draft immediately — nothing here is live until you Publish.
          </p>
          <div style={{ display: "flex", gap: 14, marginTop: 12 }}>
            <UploadWell
              assetType="logo"
              label="Logo — square mark"
              helperText="Drop SVG / PNG"
              currentUrl={draft.logo_url}
              onUploaded={loadDraft}
            />
            <UploadWell
              assetType="header"
              label="Header lockup — wide"
              helperText="Drop SVG / PNG · max 320×64"
              currentUrl={draft.header_image_url}
              onUploaded={loadDraft}
            />
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 14 }}>
            <label style={{ flex: 1 }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                Company display name
              </span>
              <input
                key={draft.updated_at ?? "unset"}
                defaultValue={draft.company_display_name ?? ""}
                onBlur={(event) =>
                  void saveDraftFields({ company_display_name: event.target.value || null })
                }
                style={{ display: "block", width: "100%", marginTop: 7 }}
              />
            </label>
            <UploadWell
              assetType="favicon"
              label="Favicon"
              helperText=""
              currentUrl={draft.favicon_url}
              onUploaded={loadDraft}
              compact
            />
            <UploadWell
              assetType="login_backdrop"
              label="Login backdrop"
              helperText=""
              currentUrl={draft.login_backdrop_url}
              onUploaded={loadDraft}
              compact
            />
          </div>
        </Card>

        <Card title="Palette & type">
          <div>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Accent</span>
            <div style={{ display: "flex", gap: 7, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
              {ACCENT_PRESETS.map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={`Use accent ${color}`}
                  onClick={() => void saveDraftFields({ accent_color: color })}
                  style={{
                    width: 30,
                    height: 30,
                    background: color,
                    border: "1px solid var(--border)",
                    outline: draft.accent_color === color ? "2px solid var(--text-h)" : "none",
                    outlineOffset: 2,
                    cursor: "pointer",
                    borderRadius: 4,
                  }}
                />
              ))}
              {draft.accent_color && !ACCENT_PRESETS.includes(draft.accent_color) && (
                <button
                  type="button"
                  aria-label={`Custom accent ${draft.accent_color}`}
                  onClick={() => customColorInputRef.current?.click()}
                  style={{
                    width: 30,
                    height: 30,
                    background: draft.accent_color,
                    border: "1px solid var(--border)",
                    outline: "2px solid var(--text-h)",
                    outlineOffset: 2,
                    cursor: "pointer",
                    borderRadius: 4,
                  }}
                />
              )}
              <button
                type="button"
                aria-label="Pick a custom accent color"
                title="Pick a custom color"
                onClick={() => customColorInputRef.current?.click()}
                style={{
                  width: 30,
                  height: 30,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "transparent",
                  border: "1px dashed var(--border)",
                  color: "var(--text-muted)",
                  cursor: "pointer",
                  borderRadius: 4,
                  fontSize: "var(--text-base)",
                  lineHeight: 1,
                }}
              >
                +
              </button>
              <input
                ref={customColorInputRef}
                aria-label="Custom accent color"
                type="color"
                value={draft.accent_color ?? "#b68235"}
                onChange={(event) => void saveDraftFields({ accent_color: event.target.value })}
                style={{ width: 0, height: 0, padding: 0, border: "none", opacity: 0 }}
              />
              {draft.accent_color && (
                <button
                  type="button"
                  onClick={() => void saveDraftFields({ accent_color: null })}
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--text-muted)",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    textDecoration: "underline",
                    padding: 0,
                  }}
                >
                  Reset to default
                </button>
              )}
            </div>
          </div>

          <div style={{ display: "flex", gap: 14, marginTop: 16, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                Header background
              </span>
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                {HEADER_BACKGROUND_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => void saveDraftFields({ header_background: option.value })}
                    style={{
                      fontSize: "var(--text-xs)",
                      padding: "3px 10px",
                      borderRadius: 999,
                      border: `1px solid ${draft.header_background === option.value ? "var(--text-h)" : "var(--border)"}`,
                      background: "transparent",
                      color:
                        draft.header_background === option.value ? "var(--text-h)" : "var(--text-muted)",
                      cursor: "pointer",
                    }}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ flex: 1, minWidth: 160 }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Typeface</span>
              <select
                value={draft.typeface}
                onChange={(event) =>
                  void saveDraftFields({ typeface: event.target.value as Typeface })
                }
                style={{ display: "block", width: "100%", marginTop: 8 }}
              >
                {TYPEFACE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ flex: 1, minWidth: 160 }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                Custom domain
              </span>
              <input
                key={draft.updated_at ?? "unset"}
                defaultValue={draft.custom_domain ?? ""}
                placeholder="crm.tenant.com"
                onBlur={(event) => void saveDraftFields({ custom_domain: event.target.value || null })}
                style={{ display: "block", width: "100%", marginTop: 8 }}
              />
              <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: "4px 0 0" }}>
                Saved, but not yet active — no routing is wired to this yet.
              </p>
            </div>
          </div>

          {draft.accent_color && (
            <div
              style={{
                marginTop: 14,
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: 10,
                display: "flex",
                gap: 11,
                alignItems: "flex-start",
              }}
            >
              <span
                style={{
                  fontSize: "var(--text-xs)",
                  fontWeight: "var(--weight-medium)",
                  padding: "2px 8px",
                  borderRadius: "var(--radius-sm)",
                  background:
                    ratio !== undefined && ratio < WCAG_AA_CONTRAST
                      ? "var(--danger-bg)"
                      : "var(--success-bg)",
                  color: ratio !== undefined && ratio < WCAG_AA_CONTRAST ? "var(--danger)" : "var(--success)",
                }}
              >
                {ratio !== undefined && ratio < WCAG_AA_CONTRAST ? "Low contrast" : "Check"}
              </span>
              <div>
                <div style={{ fontSize: "var(--text-sm)" }}>
                  {ratio !== undefined ? `${ratio.toFixed(2)}:1` : "—"}
                  {ratio !== undefined && ratio < WCAG_AA_CONTRAST && ` (WCAG AA wants ${WCAG_AA_CONTRAST}:1)`}
                </div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                  Contrast of accent on header background
                </span>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div style={{ width: 392, flex: "none", display: "flex", flexDirection: "column", gap: 14 }}>
        <BrandingLivePreview draft={draft} />
        <BrandingVersionHistory versions={versions} onRestored={() => void handleRestored()} />
      </div>
    </div>
  );
}
