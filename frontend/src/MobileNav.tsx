import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { useMe } from "./useMe";

interface NavItem {
  to: string;
  label: string;
  glyph: string;
}

// Same five destinations as design_handoff_crm_wireframes/ screen 13
// (Home/Pipe/Contact/Tasks/More) — plain Unicode glyphs, not an icon
// library dependency, same convention ThemeToggle.tsx already
// established for this app.
const TABS: NavItem[] = [
  { to: "/dashboard", label: "Home", glyph: "⌂" },
  { to: "/pipeline", label: "Pipe", glyph: "▤" },
  { to: "/contacts", label: "Contact", glyph: "◈" },
  { to: "/tasks", label: "Tasks", glyph: "☑" },
];

interface MoreLink {
  to: string;
  label: string;
  requiresTeam?: boolean;
  requiresAdmin?: boolean;
}

const MORE_LINKS: MoreLink[] = [
  { to: "/escalations", label: "Escalations", requiresTeam: true },
  { to: "/follow-ups", label: "Follow-ups", requiresTeam: true },
  { to: "/workflow-rules", label: "Workflow rules", requiresTeam: true },
  { to: "/configurations", label: "Configurations", requiresAdmin: true },
];

/** Bottom tab bar replacing Sidebar below 900px — every primary nav
 * destination Sidebar.tsx exposes stays reachable, just relocated: the 4
 * highest-traffic destinations get their own tab, everything else
 * (role-gated the same way Sidebar's Team/Admin groups are) sits behind
 * "More". */
export function MobileNav() {
  const { me } = useMe();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);

  const showTeam = me && me.user.role !== "counselor";
  const showAdmin = me?.user.role === "admin";
  const visibleMoreLinks = MORE_LINKS.filter(
    (link) => (!link.requiresTeam || showTeam) && (!link.requiresAdmin || showAdmin),
  );
  const moreActive = visibleMoreLinks.some((link) => location.pathname.startsWith(link.to));

  return (
    <>
      {moreOpen && (
        <div
          data-testid="mobile-nav-backdrop"
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", zIndex: 40 }}
          onClick={() => setMoreOpen(false)}
        >
          <div
            role="menu"
            aria-label="More"
            onClick={(event) => event.stopPropagation()}
            style={{
              position: "fixed",
              left: 0,
              right: 0,
              bottom: 56,
              background: "var(--elevation-2)",
              borderTop: "1px solid var(--border)",
              borderRadius: "var(--radius-lg) var(--radius-lg) 0 0",
              boxShadow: "var(--shadow-md)",
              padding: "var(--space-3)",
              display: "flex",
              flexDirection: "column",
              gap: 2,
            }}
          >
            {visibleMoreLinks.length === 0 && (
              <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", margin: "var(--space-2)" }}>
                Nothing else here yet
              </p>
            )}
            {visibleMoreLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMoreOpen(false)}
                style={({ isActive }) => ({
                  display: "block",
                  padding: "var(--space-3) var(--space-2)",
                  borderRadius: "var(--radius)",
                  background: isActive ? "var(--accent-subtle)" : "transparent",
                  color: isActive ? "var(--text-h)" : "var(--text)",
                  fontWeight: isActive ? "var(--weight-semibold)" : "var(--weight-normal)",
                  textDecoration: "none",
                  fontSize: "var(--text-sm)",
                })}
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        </div>
      )}

      <nav
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          height: 56,
          display: "flex",
          background: "var(--surface)",
          borderTop: "1px solid var(--border)",
          zIndex: 30,
        }}
      >
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) => `mobile-nav-tab${isActive ? " active" : ""}`}
          >
            <span aria-hidden="true" style={{ fontSize: 16, lineHeight: 1 }}>
              {tab.glyph}
            </span>
            {tab.label}
          </NavLink>
        ))}
        <button
          type="button"
          className={`mobile-nav-tab${moreActive || moreOpen ? " active" : ""}`}
          aria-haspopup="menu"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((open) => !open)}
        >
          <span aria-hidden="true" style={{ fontSize: 16, lineHeight: 1 }}>
            ⋯
          </span>
          More
        </button>
      </nav>
    </>
  );
}
