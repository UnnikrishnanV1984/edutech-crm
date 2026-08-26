import { useEffect, useRef, useState } from "react";

import { useAuth } from "./auth/context";
import { HEADER_BACKGROUND_COLORS } from "./branding/colorUtils";
import { Avatar } from "./components/Avatar";
import { useBranding } from "./useBranding";
import { useMe } from "./useMe";

/** Full-width bar above the Sidebar+main row — logo/company name on the
 * left, the tenant's header image (if any) as the bar's own background so
 * it runs the full page width rather than being confined to the 220px
 * sidebar column, and the signed-in user's avatar/logout on the right.
 * Previously all of this lived inside Sidebar.tsx, which also meant a
 * "header_background: accent" choice painted the *entire* left nav
 * (including nav links) accent-colored — moving it here scopes that
 * choice to just this bar, and Sidebar's nav links keep their own
 * existing accent-subtle-background + left-border "selected" treatment
 * (Sidebar.tsx's linkStyle) as the only other place accent color shows up. */
export function TopBar() {
  const { logout } = useAuth();
  const { me } = useMe();
  const { branding } = useBranding();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  // Same "nothing published yet" guard as the old Sidebar version — an
  // unbranded tenant (or branding still loading) must render the plain
  // default, never a partial/hardcoded theme leak.
  const displayName = branding?.company_display_name ?? undefined;
  const headerBackground = branding?.updated_at
    ? branding.header_background === "accent"
      ? (branding.accent_color ?? "var(--surface)")
      : (HEADER_BACKGROUND_COLORS[branding.header_background] ?? "var(--surface)")
    : "var(--surface)";
  const hasHeaderImage = Boolean(branding?.header_image_url);

  return (
    <header
      style={{
        height: 56,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 var(--space-4)",
        borderBottom: "1px solid var(--border)",
        backgroundColor: headerBackground,
        backgroundImage: hasHeaderImage ? `url(${branding!.header_image_url})` : undefined,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: hasHeaderImage ? "4px 10px" : 0,
          borderRadius: "var(--radius)",
          background: hasHeaderImage ? "rgba(0, 0, 0, 0.4)" : "transparent",
          minWidth: 0,
        }}
      >
        {branding?.logo_url && (
          <img
            src={branding.logo_url}
            alt={displayName ?? "Tenant logo"}
            style={{
              width: 28,
              height: 28,
              borderRadius: "var(--radius-sm)",
              objectFit: "cover",
              flexShrink: 0,
            }}
          />
        )}
        <strong
          style={{
            fontSize: "var(--text-lg)",
            color: hasHeaderImage ? "#ffffff" : "var(--text-h)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {displayName ?? "OpenFunnel"}
        </strong>
      </div>

      {me && (
        <div ref={menuRef} style={{ position: "relative" }}>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label="Account menu"
            onClick={() => setMenuOpen((open) => !open)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              padding: "var(--space-1) var(--space-2)",
              borderRadius: "var(--radius)",
            }}
          >
            <Avatar name={me.user.full_name ?? me.user.email} size={30} />
          </button>

          {menuOpen && (
            <div
              role="menu"
              style={{
                position: "absolute",
                top: "calc(100% + 6px)",
                right: 0,
                minWidth: 200,
                background: "var(--elevation-2)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "var(--shadow-md)",
                padding: "var(--space-2)",
                zIndex: 20,
              }}
            >
              <div style={{ padding: "var(--space-2) var(--space-2) var(--space-3)" }}>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--text-h)" }}>
                  {me.user.full_name ?? me.user.email}
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                  {me.tenant.name}
                </div>
              </div>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "var(--space-2)",
                  borderRadius: "var(--radius)",
                  border: "none",
                  borderTop: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--text)",
                  cursor: "pointer",
                  fontSize: "var(--text-sm)",
                }}
              >
                Log out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
