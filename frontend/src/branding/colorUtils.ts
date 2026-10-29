// Small, self-contained color math for the Branding tab's palette
// controls — no existing utility in this codebase to reuse. Deliberately
// simple RGB-space blending for lighten/darken (not perceptual HSL), good
// enough for deriving a hover/subtle shade from one admin-picked accent;
// the WCAG contrast math below is the part that has to be exact.

export interface Rgb {
  r: number;
  g: number;
  b: number;
}

const HEX_RE = /^#([0-9a-fA-F]{6})$/;

export function isValidHexColor(value: string): boolean {
  return HEX_RE.test(value);
}

export function hexToRgb(hex: string): Rgb | undefined {
  const match = HEX_RE.exec(hex);
  if (!match) return undefined;
  const int = parseInt(match[1]!, 16);
  return { r: (int >> 16) & 255, g: (int >> 8) & 255, b: int & 255 };
}

export function rgbToHex({ r, g, b }: Rgb): string {
  const toHex = (n: number) => Math.round(Math.min(255, Math.max(0, n))).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

// blend(hex, target, amount) moves hex toward target (white/black) by
// amount in [0, 1] — amount=0 returns hex unchanged, amount=1 returns
// target.
function blend(hex: string, target: Rgb, amount: number): string {
  const rgb = hexToRgb(hex);
  if (!rgb) return hex;
  return rgbToHex({
    r: rgb.r + (target.r - rgb.r) * amount,
    g: rgb.g + (target.g - rgb.g) * amount,
    b: rgb.b + (target.b - rgb.b) * amount,
  });
}

export function darken(hex: string, amount = 0.2): string {
  return blend(hex, { r: 0, g: 0, b: 0 }, amount);
}

export function lighten(hex: string, amount = 0.85): string {
  return blend(hex, { r: 255, g: 255, b: 255 }, amount);
}

// WCAG 2.x relative luminance / contrast ratio —
// https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
function relativeLuminance(rgb: Rgb): number {
  const channel = (value: number) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b);
}

// Returns undefined if either hex is invalid, rather than throwing —
// callers (a live-updating contrast check as the admin types) need to
// tolerate a momentarily-incomplete color.
export function contrastRatio(hexA: string, hexB: string): number | undefined {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  if (!a || !b) return undefined;
  const lA = relativeLuminance(a);
  const lB = relativeLuminance(b);
  const lighter = Math.max(lA, lB);
  const darker = Math.min(lA, lB);
  return (lighter + 0.05) / (darker + 0.05);
}

// WCAG AA for normal text — the bar this app's own contrast check warns
// against, matching the wireframe's "Check" chip rather than inventing a
// stricter/looser threshold.
export const WCAG_AA_CONTRAST = 4.5;

export interface AccentShades {
  accent: string;
  accentHover: string;
  accentSubtle: string;
}

export function deriveAccentShades(accentHex: string): AccentShades {
  return {
    accent: accentHex,
    accentHover: darken(accentHex, 0.18),
    accentSubtle: lighten(accentHex, 0.88),
  };
}

export const HEADER_BACKGROUND_COLORS: Record<"light" | "dark" | "accent", string | undefined> = {
  // Reuses this app's own real surface tokens (index.css) rather than
  // inventing new colors — "dark" is the exact value the app's own dark
  // theme already uses for --surface.
  light: "#ffffff",
  dark: "#1e1a16",
  accent: undefined, // resolved by the caller from the tenant's own accent_color
};
