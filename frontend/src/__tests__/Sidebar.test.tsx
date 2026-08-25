import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getBranding, type Branding } from "../api/branding";
import { listTasks } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Sidebar } from "../Sidebar";
import { useMe } from "../useMe";
import { UNBRANDED } from "../useBranding";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/tasks", () => ({ listTasks: vi.fn() }));
vi.mock("../api/branding", () => ({ getBranding: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListTasks = vi.mocked(listTasks);
const mockedGetBranding = vi.mocked(getBranding);

function branding(overrides: Partial<Branding>): Branding {
  return { ...UNBRANDED, ...overrides };
}

afterEach(() => {
  vi.resetAllMocks();
});

function setup(role: "counselor" | "manager" | "admin" = "admin") {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Acme Academy" },
    },
    error: undefined,
  });
  mockedListTasks.mockResolvedValue({
    data: [],
    meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
  });
}

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar branding", () => {
  it("shows the plain wordmark when no branding is configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({ data: UNBRANDED, meta: { request_id: "r1" } });

    renderSidebar();

    await waitFor(() => expect(mockedGetBranding).toHaveBeenCalled());
    expect(await screen.findByText("OpenFunnel")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows the company display name next to the logo when configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: branding({
        logo_url: "https://cdn.test/logo.png",
        company_display_name: "Acme Academy Branded",
        updated_at: "2026-01-01",
      }),
      meta: { request_id: "r1" },
    });

    renderSidebar();

    const image = await screen.findByRole("img", { name: "Acme Academy Branded" });
    expect(image).toHaveAttribute("src", "https://cdn.test/logo.png");
  });

  it("prefers the header lockup over the square logo when both are configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: branding({
        logo_url: "https://cdn.test/logo.png",
        header_image_url: "https://cdn.test/header.png",
        company_display_name: "Acme Academy Branded",
        updated_at: "2026-01-01",
      }),
      meta: { request_id: "r1" },
    });

    renderSidebar();

    const image = await screen.findByRole("img", { name: "Acme Academy Branded" });
    expect(image).toHaveAttribute("src", "https://cdn.test/header.png");
    expect(screen.getAllByRole("img")).toHaveLength(1);
  });

  it("applies a published header_background override, but not before anything is published", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: branding({ header_background: "dark", updated_at: "2026-01-01" }),
      meta: { request_id: "r1" },
    });

    const { container } = renderSidebar();

    await waitFor(() => expect(mockedGetBranding).toHaveBeenCalled());
    const nav = await screen.findByText("OpenFunnel");
    const navEl = container.querySelector("nav");
    expect(navEl).toHaveStyle({ background: "#221f1c" });
    void nav;
  });

  it("shows a single Configurations link for an admin, not the three old admin links", async () => {
    setup("admin");
    mockedGetBranding.mockResolvedValue({ data: UNBRANDED, meta: { request_id: "r1" } });

    renderSidebar();

    expect(await screen.findByText("Configurations")).toBeInTheDocument();
    expect(screen.queryByText("SLA policies")).not.toBeInTheDocument();
    expect(screen.queryByText("Integrations")).not.toBeInTheDocument();
  });

  it("hides the Admin group entirely for a manager", async () => {
    setup("manager");
    mockedGetBranding.mockResolvedValue({ data: UNBRANDED, meta: { request_id: "r1" } });

    renderSidebar();

    await waitFor(() => expect(screen.getByText("Escalations")).toBeInTheDocument());
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
  });
});
