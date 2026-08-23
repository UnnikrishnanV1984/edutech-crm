interface SkeletonProps {
  width?: string | number;
  height?: string | number;
}

export function Skeleton({ width = "100%", height = 16 }: SkeletonProps) {
  return (
    <span
      style={{
        display: "block",
        width,
        height,
        borderRadius: "var(--radius)",
        background: "var(--surface)",
        opacity: 0.7,
      }}
    />
  );
}
