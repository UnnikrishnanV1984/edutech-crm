import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "text";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variantStyles: Record<Variant, React.CSSProperties> = {
  primary: { background: "var(--accent)", color: "var(--accent-fg)", borderColor: "var(--accent)" },
  secondary: { background: "transparent", color: "var(--text-h)" },
  text: { background: "transparent", color: "var(--accent)", border: "none", padding: "4px 6px" },
};

export function Button({ variant = "secondary", style, ...props }: ButtonProps) {
  return <button {...props} style={{ ...variantStyles[variant], ...style }} />;
}
