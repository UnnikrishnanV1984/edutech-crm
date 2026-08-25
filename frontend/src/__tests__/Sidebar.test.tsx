import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getBranding } from "../api/branding";
import { listTasks } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Sidebar } from "../Sidebar";
import { useMe } from "../useMe";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/tasks", () => ({ listTasks: vi.fn() }));
vi.mock("../api/branding", () => ({ getBranding: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListTasks = vi.mocked(listTasks);
const mockedGetBranding = vi.mocked(getBranding);

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
    mockedGetBranding.mockResolvedValue({
      data: { logo_url: null, header_image_url: null, updated_at: null },
      meta: { request_id: "r1" },
    });

    renderSidebar();

    await waitFor(() => expect(mockedGetBranding).toHaveBeenCalled());
    expect(await screen.findByText("OpenFunnel")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows the tenant name next to the logo when only a logo is configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: { logo_url: "https://cdn.test/logo.png", header_image_url: null, updated_at: "2026-01-01" },
      meta: { request_id: "r1" },
    });

    renderSidebar();

    const image = await screen.findByRole("img", { name: "Acme Academy" });
    expect(image).toHaveAttribute("src", "https://cdn.test/logo.png");
  });

  it("prefers the header lockup over the square logo when both are configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: {
        logo_url: "https://cdn.test/logo.png",
        header_image_url: "https://cdn.test/header.png",
        updated_at: "2026-01-01",
      },
      meta: { request_id: "r1" },
    });

    renderSidebar();

    const image = await screen.findByRole("img", { name: "Acme Academy" });
    expect(image).toHaveAttribute("src", "https://cdn.test/header.png");
    expect(screen.getAllByRole("img")).toHaveLength(1);
  });

  it("shows a single Configurations link for an admin, not the three old admin links", async () => {
    setup("admin");
    mockedGetBranding.mockResolvedValue({
      data: { logo_url: null, header_image_url: null, updated_at: null },
      meta: { request_id: "r1" },
    });

    renderSidebar();

    expect(await screen.findByText("Configurations")).toBeInTheDocument();
    expect(screen.queryByText("SLA policies")).not.toBeInTheDocument();
    expect(screen.queryByText("Integrations")).not.toBeInTheDocument();
  });

  it("hides the Admin group entirely for a manager", async () => {
    setup("manager");
    mockedGetBranding.mockResolvedValue({
      data: { logo_url: null, header_image_url: null, updated_at: null },
      meta: { request_id: "r1" },
    });

    renderSidebar();

    await waitFor(() => expect(screen.getByText("Escalations")).toBeInTheDocument());
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
  });
});
