import type { TenantUser } from "../api/users";
import { userDisplayName } from "../useUsers";
import { Button } from "./Button";

interface OwnerFilterProps {
  role: string;
  meId: string;
  users: TenantUser[];
  /** undefined means "no explicit filter" — counselor's is always
   * implicitly self (server-enforced via RowScope), manager's means
   * "my team", admin's means "everyone". */
  selectedUserId: string | undefined;
  onChange: (userId: string | undefined) => void;
}

/** ADMIN_UX_IMPROVEMENTS_PLAN.md Sec5 — replaces the old single
 * Mine/Everyone toggle, which was a no-op for counselors (RowScope
 * always restricts them to self regardless of what they picked) and
 * mislabeled for managers ("Everyone" actually meant "my team"). One
 * control per role, backed by one piece of state, so a role's options
 * can never visually disagree with what the server will actually
 * return. Renders nothing for counselor — their list is always their
 * own, so there's nothing to choose. */
export function OwnerFilter({ role, meId, users, selectedUserId, onChange }: OwnerFilterProps) {
  if (role === "counselor") {
    return null;
  }

  if (role === "manager") {
    const mine = selectedUserId === meId;
    return (
      <Button variant={mine ? "primary" : "secondary"} onClick={() => onChange(mine ? undefined : meId)}>
        {mine ? "Mine" : "My team"}
      </Button>
    );
  }

  // admin
  const isEveryone = selectedUserId === undefined;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", alignItems: "center", width: "100%" }}>
      <Button
        variant={selectedUserId === meId ? "primary" : "secondary"}
        onClick={() => onChange(meId)}
      >
        Mine
      </Button>
      <select
        aria-label="Filter by owner"
        value={isEveryone ? "everyone" : selectedUserId}
        onChange={(event) => {
          const value = event.target.value;
          onChange(value === "everyone" ? undefined : value);
        }}
        style={{ flex: "1 1 auto", minWidth: 0, maxWidth: "100%" }}
      >
        <option value="everyone">Everyone</option>
        {users.map((user) => (
          <option key={user.id} value={user.id}>
            {userDisplayName(users, user.id)}
          </option>
        ))}
      </select>
    </div>
  );
}
