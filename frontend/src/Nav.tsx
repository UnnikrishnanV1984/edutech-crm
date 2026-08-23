import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { listTasks } from "./api/tasks";
import { useAuth } from "./auth/context";
import { Avatar } from "./components/Avatar";
import { Badge } from "./components/Badge";
import { ThemeToggle } from "./components/ThemeToggle";
import { useMe } from "./useMe";

// Active tab reads as a thin accent underline, not a filled pill — the one
// saturated color in the nav stays a quiet line, matching
// DESIGN_SYSTEM_REFRESH.md §10's "accent stands out because everything
// else is quiet" principle.
const linkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
  display: "inline-flex",
  alignItems: "center",
  padding: "6px 2px",
  color: isActive ? "var(--text-h)" : "var(--text)",
  borderBottom: isActive ? "2px solid var(--accent)" : "2px solid transparent",
  fontWeight: isActive ? "var(--weight-semibold)" : "var(--weight-normal)",
  textDecoration: "none",
});

export function Nav() {
  const { logout, token } = useAuth();
  const { me } = useMe();
  const [openTaskCount, setOpenTaskCount] = useState(0);

  useEffect(() => {
    if (!token || !me) {
      return;
    }
    listTasks(token, { assignee_id: me.user.id, status: "open" })
      .then((response) => setOpenTaskCount(response.meta.total))
      .catch(() => setOpenTaskCount(0));
  }, [token, me]);

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: 56,
        padding: "0 16px",
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <strong>EdTech CRM</strong>
        <NavLink to="/contacts" style={linkStyle}>
          Contacts
        </NavLink>
        <NavLink to="/pipeline" style={linkStyle}>
          Pipeline
        </NavLink>
        <NavLink to="/tasks" style={linkStyle}>
          Tasks
          {openTaskCount > 0 && (
            <span style={{ marginLeft: 6 }}>
              <Badge variant="count" label={String(openTaskCount)} />
            </span>
          )}
        </NavLink>
        {me?.user.role === "admin" && (
          <NavLink to="/integrations" style={linkStyle}>
            Integrations
          </NavLink>
        )}
      </div>
      {me && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ThemeToggle />
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>{me.tenant.name}</span>
          <Avatar name={me.user.full_name ?? me.user.email} />
          <button type="button" onClick={logout} style={{ border: "none" }}>
            Log out
          </button>
        </div>
      )}
    </nav>
  );
}
