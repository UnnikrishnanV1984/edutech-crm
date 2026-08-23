import { useEffect, useState } from "react";

import { fetchMe, type MeResponse } from "./api/bff";
import { useAuth } from "./auth/context";

export function MeShell() {
  const { token, logout } = useAuth();
  const [me, setMe] = useState<MeResponse["data"] | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!token) {
      return;
    }
    fetchMe(token)
      .then((response) => setMe(response.data))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unknown error"));
  }, [token]);

  if (error) {
    return <p role="alert">Failed to load your profile: {error}</p>;
  }

  if (!me) {
    return <p>Loading your profile…</p>;
  }

  return (
    <div>
      <h1>
        {me.user.full_name ?? me.user.email} — {me.tenant.name}
      </h1>
      <p>
        Role: {me.user.role} · Tenant: {me.tenant.slug}
      </p>
      <button type="button" onClick={logout}>
        Log out
      </button>
    </div>
  );
}
