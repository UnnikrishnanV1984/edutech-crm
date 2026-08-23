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
