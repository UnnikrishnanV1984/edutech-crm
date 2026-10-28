import { useMemo } from "react";

const DEFAULT_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

interface PagerProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
}

function Chip({
  label,
  selected,
  disabled,
  onClick,
}: {
  label: string;
  selected?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-medium)",
        padding: "4px 10px",
        borderRadius: 999,
        border: `1px solid ${selected ? "var(--text-h)" : "var(--border)"}`,
        background: "transparent",
        color: disabled ? "var(--text-muted)" : selected ? "var(--text-h)" : "var(--text-muted)",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
}

/** Shared Prev/numbered-pages/Next control + a per-page-size select, for
 * any list page backed by the API_CONVENTIONS.md §5 page/page_size
 * contract. Pulled out of ContactsListPage, which had this inline
 * first. */
export function Pager({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
}: PagerProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageNumbers = useMemo(() => {
    const windowStart = Math.max(1, Math.min(page - 2, totalPages - 4));
    return Array.from({ length: Math.min(totalPages, 5) }, (_, i) => windowStart + i);
  }, [page, totalPages]);

  if (totalPages <= 1 && !onPageSizeChange) return null;

  return (
    <div style={{ padding: "var(--space-4) 0", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <Chip label="Prev" disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))} />
      {pageNumbers.map((n) => (
        <Chip key={n} label={String(n)} selected={n === page} onClick={() => onPageChange(n)} />
      ))}
      <Chip
        label="Next"
        disabled={page >= totalPages}
        onClick={() => onPageChange(Math.min(totalPages, page + 1))}
      />
      <div style={{ flex: 1 }} />
      {onPageSizeChange && (
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
          <select
            aria-label="Rows per page"
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size} per page
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
