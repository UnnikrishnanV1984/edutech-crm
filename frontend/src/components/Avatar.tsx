import { STAGE_HUE_COUNT, toneByIndex } from "../stageColor";

interface AvatarProps {
  name: string;
  size?: number;
}

/** Deterministic hash-by-name color, cycled through the same 6-hue stage
 * sequence (DESIGN_SYSTEM_REFRESH.md §10) — gives every counselor a
 * stable, distinct pastel avatar without needing a real photo, reusing
 * the app's one hue set rather than introducing a seventh palette. */
function hashTone(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return toneByIndex(Math.abs(hash) % STAGE_HUE_COUNT);
}

export function Avatar({ name, size = 24 }: AvatarProps) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  const { bg, fg, border } = hashTone(name);

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
        background: bg,
        border: `1px solid ${border}`,
        color: fg,
        fontSize: size * 0.4,
        fontWeight: "var(--weight-semibold)",
        flexShrink: 0,
      }}
    >
      {initials || "?"}
    </span>
  );
}
