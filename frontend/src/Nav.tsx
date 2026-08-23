import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { listTasks } from "./api/tasks";
import { useAuth } from "./auth/context";
import { Avatar } from "./components/Avatar";
import { useMe } from "./useMe";

const linkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
  padding: "6px 10px",
  borderRadius: "var(--radius)",
  color: isActive ? "var(--text-h)" : "var(--text)",
  background: isActive ? "var(--surface-hover)" : "transparent",
  fontWeight: isActive ? 600 : 400,
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
            <span
              style={{
                marginLeft: 6,
                background: "var(--accent)",
                color: "var(--accent-fg)",
                borderRadius: 999,
                padding: "0 6px",
                fontSize: 11,
              }}
            >
              {openTaskCount}
            </span>
          )}
        </NavLink>
      </div>
      {me && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
