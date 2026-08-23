interface AvatarProps {
  name: string;
  size?: number;
}

export function Avatar({ name, size = 24 }: AvatarProps) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <span
      title={name}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        borderRadius: "50%",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        color: "var(--text-h)",
        fontSize: size * 0.4,
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {initials || "?"}
    </span>
  );
}
