import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ThemeToggle } from "../components/ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    delete document.documentElement.dataset.palette;
  });

  it("opens the palette popup from Light and Dark, not System", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "System" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
    expect(screen.getByRole("dialog", { name: "Choose theme" })).toBeTruthy();
  });

  it("selecting Ember applies it and closes the popup; System reverts to Meridian", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
    fireEvent.click(screen.getByRole("radio", { name: /Ember/ }));
    expect(document.documentElement.dataset.palette).toBe("ember");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "System" }));
    expect(document.documentElement.dataset.palette).toBeUndefined();
  });

  it("closes on Escape", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Light" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
