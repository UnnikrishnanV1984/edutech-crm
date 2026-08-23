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
  primary: { background: "var(--accent)", color: "var(--accent-fg)", border: "1px solid var(--accent)" },
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
