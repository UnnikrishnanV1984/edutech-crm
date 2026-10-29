import { Select } from "./Select";

// A pill-styled dropdown — matches the wireframe's "Label ▾" filter chips.
export function FilterSelect({
  placeholder,
  value,
  onChange,
  options,
}: {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <Select
      value={value}
      onChange={onChange}
      options={options}
      placeholder={placeholder}
      ariaLabel={placeholder}
      triggerStyle={{
        fontSize: "var(--text-xs)",
        padding: "4px 8px",
        borderRadius: 999,
        border: `1px solid ${value ? "var(--text-h)" : "var(--border)"}`,
        background: "transparent",
        color: value ? "var(--text-h)" : "var(--text-muted)",
      }}
    />
  );
}
