import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  discardBrandingDraft,
  listBrandingVersions,
  publishBranding,
  updateBrandingDraft,
  type BrandingDraft,
  type BrandingVersion,
} from "../api/branding";
import { getBrandingDraft } from "../api/branding";
import { useAuth } from "../auth/context";
import { BrandingTab } from "../pages/BrandingTab";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
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
const mockedGetDraft = vi.mocked(getBrandingDraft);
const mockedUpdateDraft = vi.mocked(updateBrandingDraft);
const mockedPublish = vi.mocked(publishBranding);
const mockedDiscard = vi.mocked(discardBrandingDraft);
const mockedListVersions = vi.mocked(listBrandingVersions);

const BASE_DRAFT: BrandingDraft = {
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
};

function draft(overrides: Partial<BrandingDraft> = {}): BrandingDraft {
  return { ...BASE_DRAFT, ...overrides };
}

const NO_VERSIONS: BrandingVersion[] = [];

function setup(initialDraft: BrandingDraft = BASE_DRAFT, versions: BrandingVersion[] = NO_VERSIONS) {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedGetDraft.mockResolvedValue({ data: initialDraft, meta: { request_id: "r1" } });
  mockedListVersions.mockResolvedValue({ data: versions, meta: { request_id: "r1" } });
  mockedUpdateDraft.mockImplementation((_token, updates) =>
    Promise.resolve({ data: { ...initialDraft, ...updates }, meta: { request_id: "r1" } }),
  );
  mockedPublish.mockResolvedValue({
    data: {
      logo_url: null,
      header_image_url: null,
      favicon_url: null,
      company_display_name: null,
      accent_color: null,
      header_background: "light",
      typeface: "system",
      updated_at: "2026-08-26T00:00:00Z",
    },
    meta: { request_id: "r1" },
  });
  mockedDiscard.mockResolvedValue({
    data: { ...BASE_DRAFT, updated_at: "2026-08-26T00:01:00Z" },
    meta: { request_id: "r1" },
  });
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("BrandingTab", () => {
  it("loads the draft and renders the company identity and palette sections", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    expect(screen.getByText("Company identity")).toBeInTheDocument();
    expect(screen.getByText("Palette & type")).toBeInTheDocument();
    expect(screen.getByText("Live preview")).toBeInTheDocument();
    expect(screen.getByText("Version history")).toBeInTheDocument();
  });

  it("shows a not-yet-active note next to the custom domain field", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    expect(screen.getByText(/not yet active/)).toBeInTheDocument();
  });

  it("shows preview-only notes for the login and email preview tabs", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Login"));
    expect(screen.getAllByText(/Preview only/).length).toBeGreaterThan(0);
  });

  it("picking an accent preset saves it to the draft immediately", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    fireEvent.click(screen.getByLabelText("Use accent #b68235"));

    await waitFor(() =>
      expect(mockedUpdateDraft).toHaveBeenCalledWith("test-token", { accent_color: "#b68235" }),
    );
  });

  it("flags an invalid custom hex color without saving", async () => {
    setup();
    render(<BrandingTab />);

    await screen.findByText("Company identity");
    const input = screen.getByLabelText("Custom accent color");
    fireEvent.change(input, { target: { value: "not-a-color" } });
    fireEvent.blur(input);

    expect(screen.getByText(/Must be a 6-digit hex color/)).toBeInTheDocument();
    expect(mockedUpdateDraft).not.toHaveBeenCalled();
  });

  it("warns when accent-on-header contrast is below the WCAG AA threshold", async () => {
    setup(draft({ accent_color: "#f5f0e6", header_background: "light" }));
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    expect(screen.getByText("Low contrast")).toBeInTheDocument();
  });

  it("company display name saves on blur", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    const input = screen.getByLabelText("Company display name");
    fireEvent.change(input, { target: { value: "Acme Prep" } });
    fireEvent.blur(input);

    await waitFor(() =>
      expect(mockedUpdateDraft).toHaveBeenCalledWith("test-token", {
        company_display_name: "Acme Prep",
      }),
    );
  });

  it("publishing calls the publish endpoint and refreshes version history", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Publish branding"));

    await waitFor(() => expect(mockedPublish).toHaveBeenCalledWith("test-token"));
    await waitFor(() => expect(mockedListVersions).toHaveBeenCalledTimes(2));
  });

  it("discarding resets the draft to what the endpoint returns", async () => {
    setup(draft({ company_display_name: "Unsaved Name" }));
    render(<BrandingTab />);

    await waitFor(() => expect(mockedGetDraft).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Discard"));

    await waitFor(() => expect(mockedDiscard).toHaveBeenCalledWith("test-token"));
    await waitFor(() => expect(screen.getByLabelText("Company display name")).toHaveValue(""));
  });

  it("shows an empty state in version history when nothing has been published", async () => {
    setup();
    render(<BrandingTab />);

    await waitFor(() => expect(mockedListVersions).toHaveBeenCalled());
    expect(await screen.findByText("Nothing published yet")).toBeInTheDocument();
  });

  it("marks the current version Live and offers Restore on older versions", async () => {
    setup(BASE_DRAFT, [
      {
        id: "v2",
        version_number: 2,
        published_by_name: "Admin",
        published_at: "2026-08-26T00:00:00Z",
        is_live: true,
      },
      {
        id: "v1",
        version_number: 1,
        published_by_name: "Admin",
        published_at: "2026-08-20T00:00:00Z",
        is_live: false,
      },
    ]);
    render(<BrandingTab />);

    await waitFor(() => expect(mockedListVersions).toHaveBeenCalled());
    const versionHistory = (await screen.findByText("Version history")).closest("section")!;
    expect(within(versionHistory).getByText("Live")).toBeInTheDocument();
    expect(within(versionHistory).getByText("v1")).toBeInTheDocument();
    expect(within(versionHistory).getByText("Restore")).toBeInTheDocument();
  });
});
