interface SpinnerProps {
  size?: number;
}

export function Spinner({ size = 20 }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{
        display: "inline-block",
        width: size,
        height: size,
        border: "2px solid var(--border)",
        borderTopColor: "var(--accent)",
        borderRadius: "50%",
        animation: "spin 0.7s linear infinite",
      }}
    />
  );
}

/** The centered, padded treatment for "this page/section's data hasn't
 * arrived yet" — the default gate every page uses while its primary
 * fetch is in flight. */
export function PageSpinner() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-8)" }}>
      <Spinner size={28} />
    </div>
  );
}
