import { useEffect, useRef, useState } from "react";

import {
  confirmDocument,
  getDownloadUrl,
  listDocuments,
  requestUploadUrl,
  uploadFileToS3,
  type Document,
} from "../api/documents";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";

type UploadStatus = "uploading" | "uploaded" | "failed-start" | "failed-put" | "failed-confirm";

interface UploadItem {
  localId: string;
  filename: string;
  size: number;
  status: UploadStatus;
  progress: number;
  file: File;
  s3Key?: string;
  contentType: string;
}

const FAILURE_MESSAGES: Record<string, string> = {
  "failed-start": "Couldn't start upload",
  "failed-put": "Upload failed",
  "failed-confirm": "Uploaded but couldn't save",
};

interface DocumentsSectionProps {
  contactId: string;
}

export function DocumentsSection({ contactId }: DocumentsSectionProps) {
  const { token } = useAuth();
  const [documents, setDocuments] = useState<Document[] | undefined>(undefined);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    listDocuments(token, contactId).then((response) => setDocuments(response.data));
  }, [token, contactId]);

  function updateUpload(localId: string, patch: Partial<UploadItem>) {
    setUploads((current) =>
      current.map((item) => (item.localId === localId ? { ...item, ...patch } : item)),
    );
  }

  async function runConfirm(item: UploadItem, s3Key: string, attempt = 1): Promise<void> {
    if (!token) return;
    try {
      const confirmed = await confirmDocument(token, contactId, {
        filename: item.filename,
        content_type: item.contentType,
        size_bytes: item.size,
        s3_key: s3Key,
      });
      setDocuments((current) => [confirmed.data, ...(current ?? [])]);
      setUploads((current) => current.filter((u) => u.localId !== item.localId));
    } catch {
      if (attempt < 3) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 500));
        return runConfirm(item, s3Key, attempt + 1);
      }
      updateUpload(item.localId, { status: "failed-confirm", s3Key });
    }
  }

  async function startUpload(item: UploadItem) {
    if (!token) return;
    updateUpload(item.localId, { status: "uploading", progress: 0 });
    let s3Key: string;
    try {
      const urlResponse = await requestUploadUrl(token, contactId, item.filename, item.contentType);
      s3Key = urlResponse.data.s3_key;
      try {
        await uploadFileToS3(urlResponse.data.upload_url, item.file, (percent) =>
          updateUpload(item.localId, { progress: percent }),
        );
      } catch {
        updateUpload(item.localId, { status: "failed-put" });
        return;
      }
    } catch {
      updateUpload(item.localId, { status: "failed-start" });
      return;
    }
    await runConfirm(item, s3Key);
  }

  function handleFilesSelected(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) {
      const item: UploadItem = {
        localId: crypto.randomUUID(),
        filename: file.name,
        size: file.size,
        status: "uploading",
        progress: 0,
        file,
        contentType: file.type || "application/octet-stream",
      };
      setUploads((current) => [...current, item]);
      void startUpload(item);
    }
  }

  function retry(item: UploadItem) {
    if (item.status === "failed-confirm" && item.s3Key) {
      updateUpload(item.localId, { status: "uploading" });
      void runConfirm(item, item.s3Key);
    } else {
      void startUpload(item);
    }
  }

  async function download(documentId: string) {
    if (!token) return;
    const response = await getDownloadUrl(token, documentId);
    window.open(response.data.download_url, "_blank", "noopener,noreferrer");
  }

  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: 15 }}>Documents</h2>
        <Button variant="text" onClick={() => fileInputRef.current?.click()}>
          + Upload
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          onChange={(event) => handleFilesSelected(event.target.files)}
        />
      </div>
      {documents === undefined && (
        <div style={{ padding: 8 }}>
          <Spinner size={16} />
        </div>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {uploads.map((item) => (
          <li
            key={item.localId}
            style={{
              padding: 8,
              borderBottom: "1px solid var(--border)",
              opacity: item.status === "uploading" ? 0.7 : 1,
              borderLeft:
                item.status.startsWith("failed") ? "3px solid var(--danger)" : "3px solid transparent",
            }}
          >
            <div>{item.filename}</div>
            {item.status === "uploading" && (
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                Uploading… {item.progress}%
              </div>
            )}
            {item.status.startsWith("failed") && (
              <div style={{ fontSize: 12, color: "var(--danger)", display: "flex", gap: 8 }}>
                <span>{FAILURE_MESSAGES[item.status]}</span>
                <Button variant="text" onClick={() => retry(item)}>
                  Retry
                </Button>
              </div>
            )}
          </li>
        ))}
        {documents?.map((doc) => (
          <li
            key={doc.id}
            style={{ padding: 8, borderBottom: "1px solid var(--border)" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>{doc.filename}</span>
              <Button variant="text" onClick={() => void download(doc.id)}>
                Download
              </Button>
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {Math.round(doc.size_bytes / 1024)} KB
            </div>
          </li>
        ))}
        {uploads.length === 0 && documents && documents.length === 0 && (
          <li style={{ color: "var(--text-muted)", padding: 8 }}>No documents yet</li>
        )}
      </ul>
    </section>
  );
}
