import { useCallback, useEffect, useState } from "react";

import { getBranding, type Branding } from "./api/branding";
import { useAuth } from "./auth/context";

export const UNBRANDED: Branding = {
  logo_url: null,
  header_image_url: null,
  favicon_url: null,
  company_display_name: null,
  accent_color: null,
  header_background: "light",
  typeface: "system",
  updated_at: null,
};

// undefined = not loaded yet; a Branding equal to UNBRANDED = loaded,
// nothing configured (every caller must render the same as an unbranded
// tenant in that case, never a broken partial state).
export function useBranding() {
  const { token } = useAuth();
  const [branding, setBranding] = useState<Branding | undefined>(undefined);

  const load = useCallback(() => {
    if (!token) return;
    getBranding(token)
      .then((response) => setBranding(response.data))
      .catch(() => setBranding(UNBRANDED));
  }, [token]);

  useEffect(load, [load]);

  return { branding, refetch: load };
}
