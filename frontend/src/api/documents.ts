import { apiGet, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export interface Document {
  id: string;
  contact_id: string;
  deal_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string;
  created_at: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  s3_key: string;
}

export async function requestUploadUrl(
  token: string,
  contactId: string,
  filename: string,
  contentType: string,
): Promise<DataEnvelope<UploadUrlResponse>> {
  return apiPost<DataEnvelope<UploadUrlResponse>>(
    token,
    `/api/v1/contacts/${contactId}/documents/upload-url`,
    { filename, content_type: contentType },
  );
}

/** Direct client PUT to S3/MinIO — bypasses the BFF entirely, per
 * PHASE_1_UX_FLOWS.md §4.1. Reports upload progress via onProgress since
 * fetch() has no upload-progress event; XHR does. */
export function uploadFileToS3(
  uploadUrl: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(file);
  });
}

export async function confirmDocument(
  token: string,
  contactId: string,
  input: { filename: string; content_type: string; size_bytes: number; s3_key: string; deal_id?: string },
): Promise<DataEnvelope<Document>> {
  return apiPost<DataEnvelope<Document>>(token, `/api/v1/contacts/${contactId}/documents`, input);
}

export async function listDocuments(
  token: string,
  contactId: string,
): Promise<DataEnvelope<Document[]>> {
  return apiGet<DataEnvelope<Document[]>>(token, `/api/v1/contacts/${contactId}/documents`);
}

export async function getDownloadUrl(
  token: string,
  documentId: string,
): Promise<DataEnvelope<{ download_url: string }>> {
  return apiGet<DataEnvelope<{ download_url: string }>>(
    token,
    `/api/v1/documents/${documentId}/download-url`,
  );
}
