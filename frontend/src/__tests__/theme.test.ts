import { beforeEach, describe, expect, it } from "vitest";

import { getEffectivePalette, getThemePalette, isDarkTheme, setThemePalette, setThemePreference } from "../theme";

describe("theme", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    delete document.documentElement.dataset.palette;
  });

  it("defaults to Meridian with no attributes", () => {
    expect(getThemePalette()).toBe("meridian");
    setThemePreference("system");
    expect(document.documentElement.dataset.palette).toBeUndefined();
  });

  it("applies Ember only with an explicit mode", () => {
    setThemePalette("ember");
    setThemePreference("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.palette).toBe("ember");
    setThemePreference("light");
    expect(document.documentElement.dataset.palette).toBe("ember");
  });

  it("System always resolves to Meridian but keeps the stored palette", () => {
    setThemePalette("ember");
    setThemePreference("dark");
    setThemePreference("system");
    expect(document.documentElement.dataset.palette).toBeUndefined();
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(getEffectivePalette()).toBe("meridian");
    setThemePreference("light");
    expect(document.documentElement.dataset.palette).toBe("ember");
  });

  it("isDarkTheme honors an explicit data-theme", () => {
    setThemePreference("dark");
    expect(isDarkTheme()).toBe(true);
    setThemePreference("light");
    expect(isDarkTheme()).toBe(false);
  });
});
