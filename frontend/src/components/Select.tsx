import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { createPortal } from "react-dom";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  // Overrides the default input-like trigger (border/radius/padding) —
  // used by the app's pill-shaped triggers (Move, filter chips).
  triggerStyle?: CSSProperties;
  id?: string;
  title?: string;
}

const DEFAULT_TRIGGER_STYLE: CSSProperties = {
  font: "inherit",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: "var(--space-2) var(--space-3)",
  background: "var(--bg)",
  color: "var(--text-h)",
};

// Custom div-based dropdown replacing native <select> so its open panel
// can actually be themed (rounded corners, accent hover) — browsers don't
// let you style a native select's popup consistently (see the two reverted
// attempts at doing it with CSS-only). Rendered through a portal at a
// fixed position computed from the trigger's own rect, since this
// component is used inside several scrollable/clipping containers
// (the Pipeline board's horizontally-scrolling columns, drawers, table
// cells) where an in-flow absolutely-positioned panel would get clipped.
export function Select({
  value,
  onChange,
  options,
  placeholder = "Select…",
  disabled,
  ariaLabel,
  triggerStyle,
  id,
  title,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const [rect, setRect] = useState<{ top: number; left: number; width: number } | undefined>(
    undefined,
  );
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const optionIdPrefix = useId();

  const selected = options.find((o) => o.value === value);

  const close = useCallback(() => setOpen(false), []);

  function openPanel() {
    if (disabled || options.length === 0) return;
    const el = triggerRef.current;
    if (el) {
      const r = el.getBoundingClientRect();
      setRect({ top: r.bottom + 4, left: r.left, width: r.width });
    }
    const currentIndex = options.findIndex((o) => o.value === value);
    setHighlighted(currentIndex >= 0 ? currentIndex : 0);
    setOpen(true);
  }

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      close();
    }
    // Closing on any scroll (rather than repositioning) keeps this simple
    // and avoids a stale panel drifting away from its trigger — the capture
    // phase catches scrolls inside nested containers like the Pipeline
    // board's columns, not just window scroll.
    function handleScrollOrResize() {
      close();
    }
    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [open, close]);

  function selectOption(option: SelectOption) {
    if (option.disabled) return;
    onChange(option.value);
    close();
  }

  function handleTriggerKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (disabled) return;
    if (!open) {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openPanel();
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted((i) => Math.min(options.length - 1, i + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted((i) => Math.max(0, i - 1));
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const option = options[highlighted];
      if (option) selectOption(option);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "Tab") {
      close();
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        title={title}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${optionIdPrefix}-listbox` : undefined}
        aria-activedescendant={open ? `${optionIdPrefix}-option-${highlighted}` : undefined}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={(event) => {
          // Stopped unconditionally: this is a self-contained widget, and
          // React portals bubble synthetic events through the *component*
          // tree rather than the DOM tree — without this, opening/choosing
          // from a Select nested in a clickable row (e.g. a Pipeline card)
          // would also fire that row's own onClick.
          event.stopPropagation();
          if (open) close();
          else openPanel();
        }}
        onKeyDown={handleTriggerKeyDown}
        style={{
          ...DEFAULT_TRIGGER_STYLE,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-2)",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          textAlign: "left",
          ...triggerStyle,
        }}
      >
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: selected ? "inherit" : "var(--text-muted)",
          }}
        >
          {selected ? selected.label : placeholder}
        </span>
        <span aria-hidden style={{ fontSize: "0.7em", flexShrink: 0, opacity: 0.7 }}>
          ▾
        </span>
      </button>

      {open &&
        rect &&
        createPortal(
          <div
            ref={panelRef}
            id={`${optionIdPrefix}-listbox`}
            role="listbox"
            aria-label={ariaLabel}
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
            style={{
              position: "fixed",
              top: rect.top,
              left: rect.left,
              minWidth: rect.width,
              width: "max-content",
              maxWidth: 320,
              maxHeight: 280,
              overflowY: "auto",
              background: "var(--elevation-2)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              boxShadow: "var(--shadow-md)",
              padding: "var(--space-1)",
              zIndex: 200,
            }}
          >
            {options.map((option, index) => {
              const isSelected = option.value === value;
              const isHighlighted = index === highlighted;
              return (
                <div
                  key={option.value}
                  id={`${optionIdPrefix}-option-${index}`}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={option.disabled}
                  onMouseEnter={() => setHighlighted(index)}
                  onClick={() => selectOption(option)}
                  style={{
                    padding: "var(--space-2) var(--space-3)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--text-sm)",
                    color: option.disabled ? "var(--text-muted)" : "var(--text-h)",
                    background: isHighlighted ? "var(--accent-subtle)" : "transparent",
                    cursor: option.disabled ? "not-allowed" : "pointer",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {option.label}
                </div>
              );
            })}
          </div>,
          document.body,
        )}
    </>
  );
}
