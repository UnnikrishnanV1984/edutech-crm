import { useEffect } from "react";

import { useBranding } from "../useBranding";

// Mounted once at the app shell level (App.tsx) — applies the two
// branding effects that reach beyond any single component: the accent
// color (every button/badge/link app-wide reads --accent/--accent-hover/
// --accent-subtle) and the browser-tab favicon. Sidebar.tsx handles its
// own rendering (logo/header image/company name/header background)
// directly from its own useBranding() call — this component only owns
// the two effects nothing else can express as a normal render.
export function ApplyBranding() {
  const { branding } = useBranding();

  useEffect(() => {
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    // No branding.favicon_url -> leave whatever the platform default
    // already is (set in index.html) rather than clearing it.
    if (branding?.favicon_url) {
      link.href = branding.favicon_url;
    }
  }, [branding?.favicon_url]);

  return null;
}
