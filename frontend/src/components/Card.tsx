import type { CSSProperties, ReactNode } from "react";

interface CardProps {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
}

/** The one container every dashboard section and admin-screen body should
 * render inside of — bg/border/shadow/radius give it a real edge against
 * the page background, which loose divs never had. Reused everywhere a
 * "section" needs visual separation, not just dashboards. */
export function Card({ title, action, children, style }: CardProps) {
  return (
    <section
      style={{
        background: "var(--elevation-2)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "var(--space-5)",
        ...style,
      }}
    >
      {(title || action) && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "var(--space-4)",
            gap: "var(--space-3)",
          }}
        >
          {title && (
            <h2
              style={{
                fontSize: "var(--text-lg)",
                lineHeight: "var(--line-lg)",
                fontWeight: "var(--weight-semibold)",
                color: "var(--text-h)",
                margin: 0,
              }}
            >
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
