import { useCallback, useEffect, useState } from "react";

import { getBranding, type Branding } from "./api/branding";
import { useAuth } from "./auth/context";

// undefined = not loaded yet; a Branding with both urls null = loaded,
// nothing configured (every caller must render the same as an unbranded
// tenant in that case, never a broken partial state).
export function useBranding() {
  const { token } = useAuth();
  const [branding, setBranding] = useState<Branding | undefined>(undefined);

  const load = useCallback(() => {
    if (!token) return;
    getBranding(token)
      .then((response) => setBranding(response.data))
      .catch(() => setBranding({ logo_url: null, header_image_url: null, updated_at: null }));
  }, [token]);

  useEffect(load, [load]);

  return { branding, refetch: load };
}
