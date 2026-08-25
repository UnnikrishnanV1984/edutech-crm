import { useState } from "react";

import { restoreBrandingVersion, type BrandingVersion } from "../api/branding";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";

interface BrandingVersionHistoryProps {
  versions: BrandingVersion[] | undefined;
  onRestored: () => void;
}

export function BrandingVersionHistory({ versions, onRestored }: BrandingVersionHistoryProps) {
  const { token } = useAuth();
  const [restoringId, setRestoringId] = useState<string | undefined>(undefined);

  async function restore(versionId: string) {
    if (!token) return;
    setRestoringId(versionId);
    try {
      await restoreBrandingVersion(token, versionId);
      onRestored();
    } finally {
      setRestoringId(undefined);
    }
  }

  return (
    <Card title="Version history">
      {versions && versions.length === 0 && (
        <EmptyState headline="Nothing published yet" />
      )}
      {versions && versions.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {versions.map((version) => (
            <div key={version.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Badge
                label={version.is_live ? "Live" : `v${version.version_number}`}
                tone={
                  version.is_live
                    ? { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" }
                    : undefined
                }
              />
              <div style={{ flex: 1, fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                {new Date(version.published_at).toLocaleString()}
                {version.published_by_name && ` · ${version.published_by_name}`}
              </div>
              {!version.is_live && (
                <button
                  type="button"
                  disabled={restoringId === version.id}
                  onClick={() => void restore(version.id)}
                  style={{
                    fontSize: "var(--text-xs)",
                    fontWeight: "var(--weight-medium)",
                    padding: "3px 8px",
                    borderRadius: 999,
                    border: "1px solid var(--text-h)",
                    background: "transparent",
                    color: "var(--text-h)",
                    cursor: "pointer",
                  }}
                >
                  {restoringId === version.id ? "Restoring…" : "Restore"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
