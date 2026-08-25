import { useEffect } from "react";

import { useBranding } from "../useBranding";
import { deriveAccentShades } from "./colorUtils";

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
    const styleId = "branding-accent-override";
    let styleTag = document.getElementById(styleId) as HTMLStyleElement | null;

    if (!branding?.accent_color) {
      styleTag?.remove();
      return;
    }

    const { accent, accentHover, accentSubtle } = deriveAccentShades(branding.accent_color);
    if (!styleTag) {
      styleTag = document.createElement("style");
      styleTag.id = styleId;
      document.head.appendChild(styleTag);
    }
    // A later, more specific rule than the base :root token definitions
    // in index.css — overrides the value, doesn't touch the base
    // definitions themselves, so light/dark theme switching still works
    // underneath a branding override.
    styleTag.textContent = `:root { --accent: ${accent}; --accent-hover: ${accentHover}; --accent-subtle: ${accentSubtle}; }`;

    return () => {
      styleTag?.remove();
    };
  }, [branding?.accent_color]);

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
