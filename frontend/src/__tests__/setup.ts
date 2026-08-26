import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

// Without this, the DOM from one test's render() leaks into the next
// (vitest.config.ts doesn't set test.globals, so @testing-library/react's
// own auto-cleanup registration never fires) — caught by a real failure:
// a second render() left two "Full name" labels in the DOM, and
// getByLabelText threw "multiple elements found" in an unrelated test.
afterEach(() => {
  cleanup();
});

// jsdom has no matchMedia implementation at all — useIsMobile.ts (and
// anything that renders it, which by now is most of the app shell) would
// throw "window.matchMedia is not a function" in every test without this.
// Defaults to "no match" (desktop) so existing tests render the desktop
// layout unless a test explicitly overrides matches to simulate mobile.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  });
}
