import { useRef, useState } from "react";

import { confirmBrandingAsset, requestBrandingUploadUrl, type BrandingAssetType } from "../api/branding";
import { uploadFileToS3 } from "../api/documents";
import { ApiRequestError } from "../api/client";
import { useAuth } from "../auth/context";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { useBranding } from "../useBranding";

interface UploadWellProps {
  assetType: BrandingAssetType;
  label: string;
  helperText: string;
  currentUrl: string | null | undefined;
  onUploaded: () => void;
}

function UploadWell({ assetType, label, helperText, currentUrl, onUploaded }: UploadWellProps) {
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
  const { branding, refetch } = useBranding();

  return (
    <Card title="Company identity">
      <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginTop: -8 }}>
        Uploads apply immediately across the app — there's no separate publish step.
      </p>
      <div style={{ display: "flex", gap: 14, marginTop: 12 }}>
        <UploadWell
          assetType="logo"
          label="Logo — square mark"
          helperText="Drop SVG / PNG"
          currentUrl={branding?.logo_url}
          onUploaded={refetch}
        />
        <UploadWell
          assetType="header"
          label="Header lockup — wide"
          helperText="Drop SVG / PNG · shown at the top of the sidebar"
          currentUrl={branding?.header_image_url}
          onUploaded={refetch}
        />
      </div>
    </Card>
  );
}
