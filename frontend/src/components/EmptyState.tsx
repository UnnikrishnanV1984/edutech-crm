import type { ReactNode } from "react";

interface EmptyStateProps {
  headline: string;
  subtext?: string;
  action?: ReactNode;
}

export function EmptyState({ headline, subtext, action }: EmptyStateProps) {
  return (
    <div style={{ textAlign: "center", padding: "48px 16px", color: "var(--text-muted)" }}>
      <p style={{ color: "var(--text-h)", fontWeight: 600, margin: "0 0 4px" }}>{headline}</p>
      {subtext && <p style={{ margin: "0 0 16px" }}>{subtext}</p>}
      {action}
    </div>
  );
}
