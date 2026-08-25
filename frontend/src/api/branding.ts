import { apiGet, apiPatch, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type BrandingAssetType = "logo" | "header" | "favicon" | "login_backdrop";
export type HeaderBackground = "light" | "dark" | "accent";
export type Typeface = "system" | "serif";

// The live/published surface — what the app shell actually renders.
// Deliberately narrower than BrandingDraft: login_backdrop/custom_domain
// have no real live consumer (see BrandingTab's own "where branding
// appears" checklist).
export interface Branding {
  logo_url: string | null;
  header_image_url: string | null;
  favicon_url: string | null;
  company_display_name: string | null;
  accent_color: string | null;
  header_background: HeaderBackground;
  typeface: Typeface;
  updated_at: string | null;
}

export interface BrandingDraft {
  logo_url: string | null;
  header_image_url: string | null;
  favicon_url: string | null;
  login_backdrop_url: string | null;
  company_display_name: string | null;
  accent_color: string | null;
  header_background: HeaderBackground;
  typeface: Typeface;
  custom_domain: string | null;
  updated_at: string | null;
}

export interface BrandingVersion {
  id: string;
  version_number: number;
  published_by_name: string | null;
  published_at: string;
  is_live: boolean;
}

export interface BrandingUploadUrlResponse {
  upload_url: string;
  s3_key: string;
}

export async function getBranding(token: string): Promise<DataEnvelope<Branding>> {
  return apiGet<DataEnvelope<Branding>>(token, "/api/v1/branding");
}

export async function getBrandingDraft(token: string): Promise<DataEnvelope<BrandingDraft>> {
  return apiGet<DataEnvelope<BrandingDraft>>(token, "/api/v1/branding/draft");
}

export async function updateBrandingDraft(
  token: string,
  input: Partial<{
    company_display_name: string | null;
    accent_color: string | null;
    header_background: HeaderBackground;
    typeface: Typeface;
    custom_domain: string | null;
  }>,
): Promise<DataEnvelope<BrandingDraft>> {
  return apiPatch<DataEnvelope<BrandingDraft>>(token, "/api/v1/branding/draft", input);
}

export async function requestBrandingUploadUrl(
  token: string,
  input: { asset_type: BrandingAssetType; filename: string; content_type: string },
): Promise<DataEnvelope<BrandingUploadUrlResponse>> {
  return apiPost<DataEnvelope<BrandingUploadUrlResponse>>(
    token,
    "/api/v1/branding/upload-url",
    input,
  );
}

export async function confirmBrandingAsset(
  token: string,
  input: { asset_type: BrandingAssetType; s3_key: string },
): Promise<DataEnvelope<BrandingDraft>> {
  return apiPost<DataEnvelope<BrandingDraft>>(token, "/api/v1/branding/confirm", input);
}

export async function publishBranding(token: string): Promise<DataEnvelope<Branding>> {
  return apiPost<DataEnvelope<Branding>>(token, "/api/v1/branding/publish", {});
}

export async function discardBrandingDraft(token: string): Promise<DataEnvelope<BrandingDraft>> {
  return apiPost<DataEnvelope<BrandingDraft>>(token, "/api/v1/branding/discard", {});
}

export async function listBrandingVersions(
  token: string,
): Promise<DataEnvelope<BrandingVersion[]>> {
  return apiGet<DataEnvelope<BrandingVersion[]>>(token, "/api/v1/branding/versions");
}

export async function restoreBrandingVersion(
  token: string,
  versionId: string,
): Promise<DataEnvelope<BrandingDraft>> {
  return apiPost<DataEnvelope<BrandingDraft>>(
    token,
    `/api/v1/branding/versions/${versionId}/restore`,
    {},
  );
}

export type { DataEnvelope };
