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
  type Typeface,
} from "../api/branding";
import { ApiRequestError } from "../api/client";
import { uploadFileToS3 } from "../api/documents";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import { PageSpinner, Spinner } from "../components/Spinner";
import { notifyBrandingPublished } from "../useBranding";
import { BrandingLivePreview } from "./BrandingLivePreview";
import { BrandingVersionHistory } from "./BrandingVersionHistory";

const TYPEFACE_OPTIONS: { value: Typeface; label: string }[] = [
  { value: "system", label: "System" },
  { value: "serif", label: "Serif (Georgia)" },
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
      notifyBrandingPublished();
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

  return (
    <div className="split-row">
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
          <div style={{ display: "flex", gap: 14, marginTop: 12, flexWrap: "wrap" }}>
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
          <div style={{ display: "flex", gap: 14, marginTop: 14, flexWrap: "wrap" }}>
            <label style={{ flex: 1, minWidth: 160 }}>
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

        <Card title="Type & domain">
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Typeface</span>
              <div style={{ marginTop: 8 }}>
                <Select
                  ariaLabel="Typeface"
                  value={draft.typeface}
                  onChange={(value) => void saveDraftFields({ typeface: value as Typeface })}
                  options={TYPEFACE_OPTIONS}
                  triggerStyle={{ width: "100%" }}
                />
              </div>
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

        </Card>
      </div>

      <div style={{ width: 392, maxWidth: "100%", flex: "none", display: "flex", flexDirection: "column", gap: 14 }}>
        <BrandingLivePreview draft={draft} />
        <BrandingVersionHistory versions={versions} onRestored={() => void handleRestored()} />
      </div>
    </div>
  );
}
