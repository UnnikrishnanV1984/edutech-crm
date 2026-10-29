import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "text";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variantClass: Record<Variant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  text: "btn-text",
};

const variantStyles: Record<Variant, React.CSSProperties> = {
  // Ember theme (DESIGN_SYSTEM_REFRESH.md §12): a filled gradient with dark
  // ink on top, so the primary action is the one bright thing on screen.
  // --accent-fill falls back to the flat accent when a tenant's own brand
  // color overrides it (branding/ApplyBranding.tsx).
  primary: {
    background: "var(--accent-fill, var(--accent))",
    color: "var(--accent-fg)",
    border: "none",
    fontWeight: 700,
  },
  secondary: { background: "transparent", color: "var(--text-h)" },
  text: {
    background: "transparent",
    color: "var(--accent)",
    border: "none",
    padding: "var(--space-1) 6px",
  },
};

export function Button({ variant = "secondary", className, style, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={[variantClass[variant], className].filter(Boolean).join(" ")}
      style={{ ...variantStyles[variant], ...style }}
    />
  );
}
