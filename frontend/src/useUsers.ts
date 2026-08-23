import { useEffect, useState } from "react";

import { listUsers, type TenantUser } from "./api/users";
import { useAuth } from "./auth/context";

export function useUsers() {
  const { token } = useAuth();
  const [users, setUsers] = useState<TenantUser[]>([]);

  useEffect(() => {
    if (!token) {
      return;
    }
    listUsers(token)
      .then((response) => setUsers(response.data))
      .catch(() => setUsers([]));
  }, [token]);

  return users;
}

export function userDisplayName(users: TenantUser[], userId: string): string {
  const user = users.find((u) => u.id === userId);
  return user ? (user.full_name ?? user.email) : "Unknown";
}
