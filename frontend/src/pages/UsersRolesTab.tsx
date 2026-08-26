import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { PageSpinner } from "../components/Spinner";
import { useUsers } from "../useUsers";

const ROLE_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  admin: { bg: "var(--accent-subtle)", fg: "var(--accent-hover)", border: "transparent" },
  manager: { bg: "var(--warning-bg)", fg: "var(--warning)", border: "transparent" },
  counselor: { bg: "var(--surface)", fg: "var(--text)", border: "var(--border)" },
};

// Read-only for now — editing a user's role/status here would require a
// new Keycloak admin service-account client (its own secret to
// provision), which is a genuinely new external integration, not just a
// UI panel (product decision 2026-08-25: ship the visibility this tab
// needs first, revisit editing as an explicit later scope).
export function UsersRolesTab() {
  const users = useUsers();
  const usersById = new Map(users.map((u) => [u.id, u]));

  return (
    <Card title="Users & roles">
      <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginTop: -8 }}>
        Read-only for now — changing a role or deactivating a user still has to happen in Keycloak.
      </p>
      {users.length === 0 && <PageSpinner />}
      {users.length > 0 && (
        <div className="table-scroll">
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: "var(--space-2)" }}>Name</th>
              <th style={{ padding: "var(--space-2)" }}>Email</th>
              <th style={{ padding: "var(--space-2)" }}>Role</th>
              <th style={{ padding: "var(--space-2)" }}>Manager</th>
              <th style={{ padding: "var(--space-2)" }}>Territory</th>
              <th style={{ padding: "var(--space-2)" }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "var(--space-2)" }}>{user.full_name ?? "—"}</td>
                <td style={{ padding: "var(--space-2)", color: "var(--text-muted)" }}>
                  {user.email}
                </td>
                <td style={{ padding: "var(--space-2)" }}>
                  <Badge label={user.role} tone={ROLE_TONE[user.role]} />
                </td>
                <td style={{ padding: "var(--space-2)", color: "var(--text-muted)" }}>
                  {user.manager_id
                    ? (usersById.get(user.manager_id)?.full_name ??
                      usersById.get(user.manager_id)?.email ??
                      "—")
                    : "—"}
                </td>
                <td style={{ padding: "var(--space-2)", color: "var(--text-muted)" }}>
                  {user.territory ?? "—"}
                </td>
                <td style={{ padding: "var(--space-2)" }}>
                  <Badge
                    label={user.status}
                    tone={
                      user.status === "active"
                        ? undefined
                        : { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" }
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </Card>
  );
}
