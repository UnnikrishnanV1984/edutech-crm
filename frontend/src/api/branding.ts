import { apiGet, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export type BrandingAssetType = "logo" | "header";

export interface Branding {
  logo_url: string | null;
  header_image_url: string | null;
  updated_at: string | null;
}

export interface BrandingUploadUrlResponse {
  upload_url: string;
  s3_key: string;
}

export async function getBranding(token: string): Promise<DataEnvelope<Branding>> {
  return apiGet<DataEnvelope<Branding>>(token, "/api/v1/branding");
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
): Promise<DataEnvelope<Branding>> {
  return apiPost<DataEnvelope<Branding>>(token, "/api/v1/branding/confirm", input);
}
