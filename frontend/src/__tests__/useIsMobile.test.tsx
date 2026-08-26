import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useIsMobile } from "../useIsMobile";

let listeners: Array<(event: { matches: boolean }) => void> = [];
let matches = false;

function Probe() {
  const isMobile = useIsMobile();
  return <span>{isMobile ? "mobile" : "desktop"}</span>;
}

beforeEach(() => {
  listeners = [];
  matches = false;
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: (_event: string, listener: (event: { matches: boolean }) => void) => {
      listeners.push(listener);
    },
    removeEventListener: (_event: string, listener: (event: { matches: boolean }) => void) => {
      listeners = listeners.filter((l) => l !== listener);
    },
    dispatchEvent: () => false,
  }));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useIsMobile", () => {
  it("reflects the initial matchMedia state", () => {
    matches = true;
    const { getByText } = render(<Probe />);
    expect(getByText("mobile")).toBeInTheDocument();
  });

  it("defaults to desktop when the query doesn't match", () => {
    matches = false;
    const { getByText } = render(<Probe />);
    expect(getByText("desktop")).toBeInTheDocument();
  });

  it("updates when the media query change event fires", () => {
    matches = false;
    const { getByText } = render(<Probe />);
    expect(getByText("desktop")).toBeInTheDocument();

    act(() => {
      matches = true;
      for (const listener of listeners) listener({ matches: true });
    });

    expect(getByText("mobile")).toBeInTheDocument();
  });
});
