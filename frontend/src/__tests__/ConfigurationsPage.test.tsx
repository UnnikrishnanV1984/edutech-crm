import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getBrandingDraft, listBrandingVersions } from "../api/branding";
import { listPipelineStages } from "../api/pipelineStages";
import { listSlaPolicies } from "../api/slaPolicies";
import { listUsers } from "../api/users";
import { useAuth } from "../auth/context";
import { ConfigurationsPage } from "../pages/ConfigurationsPage";
import { useMe } from "../useMe";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/pipelineStages", () => ({
  listPipelineStages: vi.fn(),
  updatePipelineStage: vi.fn(),
  createPipelineStage: vi.fn(),
  deletePipelineStage: vi.fn(),
  reorderPipelineStages: vi.fn(),
  batchUpdatePipelineStages: vi.fn(),
  resetPipelineStagesToDefault: vi.fn(),
}));
vi.mock("../api/slaPolicies", () => ({
  listSlaPolicies: vi.fn(),
  createSlaPolicy: vi.fn(),
  setSlaPolicyStatus: vi.fn(),
}));
vi.mock("../api/users", () => ({ listUsers: vi.fn() }));
vi.mock("../api/branding", () => ({
  getBrandingDraft: vi.fn(),
  updateBrandingDraft: vi.fn(),
  requestBrandingUploadUrl: vi.fn(),
  confirmBrandingAsset: vi.fn(),
  publishBranding: vi.fn(),
  discardBrandingDraft: vi.fn(),
  listBrandingVersions: vi.fn(),
  restoreBrandingVersion: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListStages = vi.mocked(listPipelineStages);
const mockedListPolicies = vi.mocked(listSlaPolicies);
const mockedListUsers = vi.mocked(listUsers);
const mockedGetBrandingDraft = vi.mocked(getBrandingDraft);
const mockedListBrandingVersions = vi.mocked(listBrandingVersions);

afterEach(() => {
  vi.resetAllMocks();
});

function setup(role: "admin" | "manager" = "admin") {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Admin", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Tenant A" },
    },
    error: undefined,
  });
  mockedListStages.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
  mockedListPolicies.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
  mockedListUsers.mockResolvedValue({
    data: [
      {
        id: "u1",
        email: "a@example.test",
        full_name: "Admin",
        role: "admin",
        manager_id: null,
        status: "active",
        territory: null,
      },
    ],
    meta: { request_id: "r1" },
  });
  mockedGetBrandingDraft.mockResolvedValue({
    data: {
      logo_url: null,
      header_image_url: null,
      favicon_url: null,
      login_backdrop_url: null,
      company_display_name: null,
      accent_color: null,
      header_background: "light",
      typeface: "system",
      custom_domain: null,
      updated_at: null,
    },
    meta: { request_id: "r1" },
  });
  mockedListBrandingVersions.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConfigurationsPage />
    </MemoryRouter>,
  );
}

describe("ConfigurationsPage", () => {
  it("shows an admins-only message for a manager", () => {
    setup("manager");
    renderPage();
    expect(screen.getByText("Admins only")).toBeInTheDocument();
  });

  it("defaults to the SLA tab", async () => {
    setup();
    renderPage();
    await waitFor(() => expect(mockedListPolicies).toHaveBeenCalled());
    expect(screen.getByText("Configured policies")).toBeInTheDocument();
  });

  it("switching to Users & roles shows a read-only user table", async () => {
    setup();
    renderPage();
    await waitFor(() => expect(mockedListPolicies).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Users & roles"));

    await waitFor(() => expect(mockedListUsers).toHaveBeenCalled());
    expect(await screen.findByText("Admin")).toBeInTheDocument();
    expect(screen.getByText(/Read-only for now/)).toBeInTheDocument();
  });

  it("switching to Branding renders the branding editor", async () => {
    setup();
    renderPage();
    await waitFor(() => expect(mockedListPolicies).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Branding"));

    await waitFor(() => expect(mockedGetBrandingDraft).toHaveBeenCalled());
    expect(await screen.findByText("Company identity")).toBeInTheDocument();
    expect(screen.getByText("Palette & type")).toBeInTheDocument();
  });
});
