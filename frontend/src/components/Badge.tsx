import type { ColorTone } from "../stageColor";

interface BadgeProps {
  label: string;
  tone?: ColorTone;
  icon?: string;
  /** "count" is the small accent-subtle pill used for the nav task-count
   * badge and section counts (DESIGN_SYSTEM_REFRESH.md §10) — `tone` is
   * ignored in this variant, it always uses the accent-subtle treatment. */
  variant?: "chip" | "count";
}

const NEUTRAL_TONE: ColorTone = { bg: "var(--surface)", fg: "var(--text)", border: "var(--border)" };

/** Pastel-chip pattern: soft tinted background + deeper same-hue text, not
 * solid color + white text (DESIGN_SYSTEM_REFRESH.md §8-§10). Color plus
 * text label always — color is never the only signal, which matters
 * doubly for pipeline stages since tenants can rename/reorder them. */
export function Badge({ label, tone, icon, variant = "chip" }: BadgeProps) {
  if (variant === "count") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          fontSize: "var(--text-xs)",
          fontWeight: "var(--weight-medium)",
          padding: "0 var(--space-2)",
          borderRadius: 999,
          background: "var(--accent-subtle)",
          color: "var(--accent)",
        }}
      >
        {label}
      </span>
    );
  }

  const { bg, fg, border } = tone ?? NEUTRAL_TONE;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-medium)",
        padding: "2px var(--space-2)",
        borderRadius: "var(--radius-sm)",
        background: bg,
        color: fg,
        border: `1px solid ${border}`,
      }}
    >
      {icon}
      {label}
    </span>
  );
}
