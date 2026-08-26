import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MobileNav } from "../MobileNav";
import { useMe } from "../useMe";

vi.mock("../useMe", () => ({ useMe: vi.fn() }));

const mockedUseMe = vi.mocked(useMe);

afterEach(() => {
  vi.resetAllMocks();
});

function setup(role: "counselor" | "manager" | "admin") {
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Acme Academy" },
    },
    error: undefined,
  });
}

function renderNav() {
  return render(
    <MemoryRouter>
      <MobileNav />
    </MemoryRouter>,
  );
}

describe("MobileNav", () => {
  it("always shows the 4 primary tabs plus More", () => {
    setup("counselor");
    renderNav();

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Pipe")).toBeInTheDocument();
    expect(screen.getByText("Contact")).toBeInTheDocument();
    expect(screen.getByText("Tasks")).toBeInTheDocument();
    expect(screen.getByText("More")).toBeInTheDocument();
  });

  it("hides Team and Admin links from More for a counselor", () => {
    setup("counselor");
    renderNav();

    fireEvent.click(screen.getByText("More"));

    expect(screen.queryByText("Escalations")).not.toBeInTheDocument();
    expect(screen.queryByText("Follow-ups")).not.toBeInTheDocument();
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
    expect(screen.getByText("Nothing else here yet")).toBeInTheDocument();
  });

  it("shows Team links but not Configurations for a manager", () => {
    setup("manager");
    renderNav();

    fireEvent.click(screen.getByText("More"));

    expect(screen.getByText("Escalations")).toBeInTheDocument();
    expect(screen.getByText("Follow-ups")).toBeInTheDocument();
    expect(screen.getByText("Workflow rules")).toBeInTheDocument();
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
  });

  it("shows every link for an admin, including Configurations", () => {
    setup("admin");
    renderNav();

    fireEvent.click(screen.getByText("More"));

    expect(screen.getByText("Escalations")).toBeInTheDocument();
    expect(screen.getByText("Configurations")).toBeInTheDocument();
  });

  it("closes the More sheet on an outside click", () => {
    setup("admin");
    renderNav();

    fireEvent.click(screen.getByText("More"));
    expect(screen.getByText("Configurations")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("mobile-nav-backdrop"));
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
  });
});
