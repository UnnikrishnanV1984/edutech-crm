import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { confirmBrandingAsset, getBranding, requestBrandingUploadUrl } from "../api/branding";
import { uploadFileToS3 } from "../api/documents";
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
vi.mock("../api/branding", () => ({
  getBranding: vi.fn(),
  requestBrandingUploadUrl: vi.fn(),
  confirmBrandingAsset: vi.fn(),
}));
vi.mock("../api/documents", () => ({ uploadFileToS3: vi.fn() }));
vi.mock("../api/users", () => ({ listUsers: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListStages = vi.mocked(listPipelineStages);
const mockedListPolicies = vi.mocked(listSlaPolicies);
const mockedGetBranding = vi.mocked(getBranding);
const mockedRequestUploadUrl = vi.mocked(requestBrandingUploadUrl);
const mockedUploadToS3 = vi.mocked(uploadFileToS3);
const mockedConfirmAsset = vi.mocked(confirmBrandingAsset);
const mockedListUsers = vi.mocked(listUsers);

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
  mockedGetBranding.mockResolvedValue({
    data: { logo_url: null, header_image_url: null, updated_at: null },
    meta: { request_id: "r1" },
  });
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

  it("switching to Branding shows the two upload wells", async () => {
    setup();
    renderPage();
    await waitFor(() => expect(mockedListPolicies).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Branding"));

    expect(await screen.findByText("Logo — square mark")).toBeInTheDocument();
    expect(screen.getByText("Header lockup — wide")).toBeInTheDocument();
  });

  it("uploading a logo requests an upload URL, PUTs to S3, and confirms", async () => {
    setup();
    mockedRequestUploadUrl.mockResolvedValue({
      data: { upload_url: "https://s3.test/put", s3_key: "t1/branding/logo/abc-logo.png" },
      meta: { request_id: "r1" },
    });
    mockedUploadToS3.mockResolvedValue(undefined);
    mockedConfirmAsset.mockResolvedValue({
      data: {
        logo_url: "https://s3.test/logo.png",
        header_image_url: null,
        updated_at: "2026-01-01T00:00:00Z",
      },
      meta: { request_id: "r1" },
    });

    renderPage();
    fireEvent.click(screen.getByText("Branding"));
    await screen.findByText("Logo — square mark");

    const file = new File(["bytes"], "logo.png", { type: "image/png" });
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fireEvent.change(fileInputs[0]!, { target: { files: [file] } });

    await waitFor(() =>
      expect(mockedRequestUploadUrl).toHaveBeenCalledWith("test-token", {
        asset_type: "logo",
        filename: "logo.png",
        content_type: "image/png",
      }),
    );
    await waitFor(() =>
      expect(mockedConfirmAsset).toHaveBeenCalledWith("test-token", {
        asset_type: "logo",
        s3_key: "t1/branding/logo/abc-logo.png",
      }),
    );
    expect(mockedGetBranding).toHaveBeenCalledTimes(2); // initial load + refetch after upload
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
});
