import { useEffect, useState } from "react";

// 899px, not 900 — the complement of index.css's own `@media
// (min-width: 900px)` breakpoint (.contact-detail-grid, .grid-2col, …),
// so a JS-driven layout branch (bottom tab bar, Pipeline's one-stage
// board) never disagrees with a CSS-driven one at exactly 900px.
const QUERY = "(max-width: 899px)";

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.matchMedia(QUERY).matches,
  );

  useEffect(() => {
    const mql = window.matchMedia(QUERY);
    // Read matches off the event itself (MediaQueryListEvent.matches),
    // not mql.matches — keeps this correct against test doubles whose
    // mql object is a one-time snapshot rather than a live-updating one.
    const onChange = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return isMobile;
}
