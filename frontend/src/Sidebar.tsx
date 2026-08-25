import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { listTasks } from "./api/tasks";
import { useAuth } from "./auth/context";
import { Avatar } from "./components/Avatar";
import { Badge } from "./components/Badge";
import { ThemeToggle } from "./components/ThemeToggle";
import { useBranding } from "./useBranding";
import { useMe } from "./useMe";

interface NavItem {
  to: string;
  label: string;
}

// Grouped rather than one flat list — the account-side groups (Team,
// Admin) only ever apply to Manager/Admin, and a labeled group reads
// faster than an unbroken column of 9 links once Staff-visible items
// (4) and role-gated ones (5) are combined.
const PRIMARY: NavItem[] = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/contacts", label: "Contacts" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/tasks", label: "Tasks" },
];
const TEAM: NavItem[] = [
  { to: "/escalations", label: "Escalations" },
  { to: "/follow-ups", label: "Follow-ups" },
  { to: "/workflow-rules", label: "Workflow rules" },
];
const ADMIN: NavItem[] = [{ to: "/configurations", label: "Configurations" }];

// Vertical nav's active state: a left accent stripe + tinted background,
// not the horizontal tab bar's underline — color plus a second cue
// (position + fill, not color alone) carries over from
// DESIGN_SYSTEM_REFRESH.md's original principle, just re-expressed for
// a vertical layout.
function linkStyle({ isActive }: { isActive: boolean }): React.CSSProperties {
  return {
    display: "block",
    padding: "var(--space-2) var(--space-3)",
    marginInline: "var(--space-2)",
    borderRadius: "var(--radius)",
    borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
    background: isActive ? "var(--accent-subtle)" : "transparent",
    color: isActive ? "var(--text-h)" : "var(--text)",
    fontWeight: isActive ? "var(--weight-semibold)" : "var(--weight-normal)",
    textDecoration: "none",
    fontSize: "var(--text-sm)",
  };
}

function GroupLabel({ children }: { children: string }) {
  return (
    <div
      style={{
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-semibold)",
        color: "var(--text-muted)",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        padding: "var(--space-4) var(--space-3) var(--space-1)",
      }}
    >
      {children}
    </div>
  );
}

export function Sidebar() {
  const { logout, token } = useAuth();
  const { me } = useMe();
  const { branding } = useBranding();
  const [openTaskCount, setOpenTaskCount] = useState(0);

  useEffect(() => {
    if (!token || !me) {
      return;
    }
    listTasks(token, { assignee_id: me.user.id, status: "open" })
      .then((response) => setOpenTaskCount(response.meta.total))
      .catch(() => setOpenTaskCount(0));
  }, [token, me]);

  const showTeam = me && me.user.role !== "counselor";
  const showAdmin = me?.user.role === "admin";

  return (
    <nav
      style={{
        width: 220,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        height: "100svh",
        background: "var(--surface)",
        borderRight: "1px solid var(--border)",
      }}
    >
      <div style={{ padding: "var(--space-4) var(--space-3)" }}>
        {branding?.header_image_url ? (
          <img
            src={branding.header_image_url}
            alt={me?.tenant.name ?? "Tenant logo"}
            style={{ maxWidth: "100%", maxHeight: 32, display: "block" }}
          />
        ) : branding?.logo_url ? (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <img
              src={branding.logo_url}
              alt={me?.tenant.name ?? "Tenant logo"}
              style={{ width: 28, height: 28, borderRadius: "var(--radius-sm)", objectFit: "cover" }}
            />
            <strong style={{ fontSize: "var(--text-lg)", color: "var(--text-h)" }}>
              {me?.tenant.name ?? "OpenFunnel"}
            </strong>
          </div>
        ) : (
          <strong style={{ fontSize: "var(--text-lg)", color: "var(--text-h)" }}>OpenFunnel</strong>
        )}
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", paddingBottom: "var(--space-3)" }}>
        <GroupLabel>Workspace</GroupLabel>
        {PRIMARY.map((item) => (
          <NavLink key={item.to} to={item.to} style={linkStyle}>
            {item.label}
            {item.to === "/tasks" && openTaskCount > 0 && (
              <span style={{ marginLeft: 6 }}>
                <Badge variant="count" label={String(openTaskCount)} />
              </span>
            )}
          </NavLink>
        ))}

        {showTeam && (
          <>
            <GroupLabel>Team</GroupLabel>
            {TEAM.map((item) => (
              <NavLink key={item.to} to={item.to} style={linkStyle}>
                {item.label}
              </NavLink>
            ))}
          </>
        )}

        {showAdmin && (
          <>
            <GroupLabel>Admin</GroupLabel>
            {ADMIN.map((item) => (
              <NavLink key={item.to} to={item.to} style={linkStyle}>
                {item.label}
              </NavLink>
            ))}
          </>
        )}
      </div>

      {me && (
        <div
          style={{
            padding: "var(--space-3)",
            borderTop: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-3)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Avatar name={me.user.full_name ?? me.user.email} />
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: "var(--text-sm)",
                  color: "var(--text-h)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {me.user.full_name ?? me.user.email}
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                {me.tenant.name}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <ThemeToggle />
            <button type="button" onClick={logout} style={{ border: "none" }}>
              Log out
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
