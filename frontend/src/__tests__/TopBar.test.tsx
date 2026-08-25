import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getBranding, type Branding } from "../api/branding";
import { useAuth } from "../auth/context";
import { TopBar } from "../TopBar";
import { UNBRANDED } from "../useBranding";
import { useMe } from "../useMe";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/branding", () => ({ getBranding: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedGetBranding = vi.mocked(getBranding);

function branding(overrides: Partial<Branding>): Branding {
  return { ...UNBRANDED, ...overrides };
}

afterEach(() => {
  vi.resetAllMocks();
});

function setup() {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role: "admin", status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Acme Academy" },
    },
    error: undefined,
  });
}

describe("TopBar branding", () => {
  it("shows the plain wordmark and no logo when no branding is configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({ data: UNBRANDED, meta: { request_id: "r1" } });

    render(<TopBar />);

    await waitFor(() => expect(mockedGetBranding).toHaveBeenCalled());
    expect(await screen.findByText("OpenFunnel")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows the logo next to the company display name when configured", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: branding({
        logo_url: "https://cdn.test/logo.png",
        company_display_name: "Acme Academy Branded",
        updated_at: "2026-01-01",
      }),
      meta: { request_id: "r1" },
    });

    render(<TopBar />);

    expect(await screen.findByText("Acme Academy Branded")).toBeInTheDocument();
    const image = screen.getByRole("img", { name: "Acme Academy Branded" });
    expect(image).toHaveAttribute("src", "https://cdn.test/logo.png");
  });

  it("shows the logo and company name together even when a header image is also configured", async () => {
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

    render(<TopBar />);

    expect(await screen.findByText("Acme Academy Branded")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Acme Academy Branded" })).toHaveAttribute(
      "src",
      "https://cdn.test/logo.png",
    );
  });

  it("applies a published header_background override, but not before anything is published", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: branding({ header_background: "dark", updated_at: "2026-01-01" }),
      meta: { request_id: "r1" },
    });

    const { container } = render(<TopBar />);

    await waitFor(() => expect(mockedGetBranding).toHaveBeenCalled());
    await screen.findByText("OpenFunnel");
    const header = container.querySelector("header");
    expect(header).toHaveStyle({ backgroundColor: "#221f1c" });
  });

  it("does not apply a header_background before anything has been published", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({
      data: branding({ header_background: "dark" }),
      meta: { request_id: "r1" },
    });

    const { container } = render(<TopBar />);

    await waitFor(() => expect(mockedGetBranding).toHaveBeenCalled());
    await screen.findByText("OpenFunnel");
    expect(container.querySelector("header")).toHaveStyle({ backgroundColor: "var(--surface)" });
  });
});

describe("TopBar account menu", () => {
  it("opens the account menu and logs out", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({ data: UNBRANDED, meta: { request_id: "r1" } });
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout });

    render(<TopBar />);

    expect(screen.queryByText("Log out")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Account menu"));

    expect(await screen.findByText("Log out")).toBeInTheDocument();
    expect(screen.getByText("Acme Academy")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Log out"));
    expect(logout).toHaveBeenCalled();
  });

  it("closes the account menu on an outside click", async () => {
    setup();
    mockedGetBranding.mockResolvedValue({ data: UNBRANDED, meta: { request_id: "r1" } });

    render(<TopBar />);

    fireEvent.click(screen.getByLabelText("Account menu"));
    expect(await screen.findByText("Log out")).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByText("Log out")).not.toBeInTheDocument());
  });
});
