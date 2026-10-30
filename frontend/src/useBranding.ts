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

// Fired by BrandingTab after a successful publish. TopBar and
// ApplyBranding each hold their own independent useBranding() state
// fetched once on mount, with no shared store between them — without
// this, publishing leaves both showing the pre-publish branding until a
// full page reload remounts them.
const BRANDING_PUBLISHED_EVENT = "branding:published";

export function notifyBrandingPublished() {
  window.dispatchEvent(new Event(BRANDING_PUBLISHED_EVENT));
}

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

  useEffect(() => {
    window.addEventListener(BRANDING_PUBLISHED_EVENT, load);
    return () => window.removeEventListener(BRANDING_PUBLISHED_EVENT, load);
  }, [load]);

  return { branding, refetch: load };
}
