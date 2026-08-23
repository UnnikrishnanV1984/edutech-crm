import { useEffect, useState } from "react";

import { fetchMe, type MeResponse } from "./api/bff";
import { useAuth } from "./auth/context";

export function useMe() {
  const { token } = useAuth();
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

  return { me, error };
}
