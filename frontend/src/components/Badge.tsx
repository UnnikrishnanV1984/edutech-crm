interface BadgeProps {
  label: string;
  color?: string;
  icon?: string;
}

/** Color plus text label always — color is never the only signal
 * (PHASE_1_UI_DESIGN.md's standing rule), which matters doubly for
 * pipeline stages since tenants can rename/reorder them. */
export function Badge({ label, color, icon }: BadgeProps) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 12,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 999,
        background: color ? `${color}22` : "var(--surface)",
        color: color ?? "var(--text)",
        border: `1px solid ${color ? `${color}55` : "var(--border)"}`,
      }}
    >
      {icon}
      {label}
    </span>
  );
}
