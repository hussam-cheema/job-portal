"use client";

import { DragEvent, useEffect, useRef, useState } from "react";
import {
  downloadDocumentConversion,
  fetchDocumentConversion,
  startDocumentConversion,
} from "@/lib/api";
import type { DocumentConversionJob } from "@/lib/types";

const MAX_BYTES = 10 * 1024 * 1024;

function fileError(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension !== "pdf" && extension !== "docx") {
    return "This document type is not allowed. Choose one PDF or DOCX file.";
  }
  if (file.size >= MAX_BYTES) {
    return "The document must be smaller than 10 MB.";
  }
  if (!file.size) return "The selected document is empty.";
  return null;
}

function readableSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function direction(file: File | null): string {
  return file?.name.toLowerCase().endsWith(".pdf") ? "PDF → DOCX" : "DOCX → PDF";
}

export function DocumentConverter() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [job, setJob] = useState<DocumentConversionJob | null>(null);
  const [token, setToken] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const runId = useRef(0);

  useEffect(() => () => { runId.current += 1; }, []);

  function chooseFile(candidate: File | null) {
    runId.current += 1;
    setJob(null);
    setToken("");
    setError("");
    if (!candidate) {
      setFile(null);
      return;
    }
    const validationError = fileError(candidate);
    if (validationError) {
      setFile(null);
      setError(validationError);
      return;
    }
    setFile(candidate);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files.length !== 1) {
      setError("Upload exactly one document at a time.");
      setFile(null);
      return;
    }
    chooseFile(event.dataTransfer.files[0]);
  }

  async function download(jobToDownload: DocumentConversionJob, accessToken: string) {
    const blob = await downloadDocumentConversion(jobToDownload.job_id, accessToken);
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = jobToDownload.output_filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
  }

  async function convert() {
    if (!file) return;
    const validationError = fileError(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    const currentRun = ++runId.current;
    setError("");
    setJob({
      job_id: "uploading",
      status: "queued",
      progress: 8,
      stage: "Uploading securely",
      input_format: file.name.toLowerCase().endsWith(".pdf") ? "pdf" : "docx",
      output_format: file.name.toLowerCase().endsWith(".pdf") ? "docx" : "pdf",
      output_filename: "",
      estimated_seconds_remaining: null,
      created_at: new Date().toISOString(),
      expires_at: new Date().toISOString(),
    });
    try {
      const created = await startDocumentConversion(file);
      if (runId.current !== currentRun) return;
      const accessToken = created.access_token;
      setToken(accessToken);
      let current: DocumentConversionJob = created;
      setJob(current);
      while (current.status === "queued" || current.status === "converting" || current.status === "verifying") {
        await new Promise((resolve) => window.setTimeout(resolve, 750));
        if (runId.current !== currentRun) return;
        current = await fetchDocumentConversion(created.job_id, accessToken);
        setJob(current);
      }
      if (current.status === "failed") {
        setError(current.error || "The document could not be converted.");
        return;
      }
      await download(current, accessToken);
    } catch (caught) {
      if (runId.current !== currentRun) return;
      setError(caught instanceof Error ? caught.message : "The document could not be converted.");
      setJob(null);
    }
  }

  const busy = Boolean(job && ["queued", "converting", "verifying"].includes(job.status));

  return (
    <section className="document-converter" data-testid="document-converter">
      <div className="document-converter-intro">
        <div>
          <p className="tool-kicker">Private, temporary processing</p>
          <h2>Convert a document</h2>
          <p>Upload one file and the converter automatically selects PDF or DOCX as the output.</p>
        </div>
        <div className="document-converter-direction" aria-label="Conversion direction">
          <span>{file ? direction(file).split(" → ")[0] : "PDF"}</span>
          <b aria-hidden="true">→</b>
          <span>{file ? direction(file).split(" → ")[1] : "DOCX"}</span>
        </div>
      </div>

      <label
        htmlFor="document-converter-file"
        className={`document-dropzone${isDragging ? " is-dragging" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          id="document-converter-file"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => chooseFile(event.target.files?.[0] || null)}
          disabled={busy}
        />
        <span className="document-dropzone-icon" aria-hidden="true">⇧</span>
        <strong>{file ? file.name : "Drop a PDF or DOCX here"}</strong>
        <span>{file ? `${readableSize(file.size)} · ${direction(file)}` : "or click to choose a document"}</span>
        <small>One document only. The file must be smaller than 10 MB.</small>
      </label>

      {error && <div className="document-converter-message is-error" role="alert">{error}</div>}

      {job && (
        <div className={`document-converter-progress is-${job.status}`} aria-live="polite">
          <div className="document-progress-copy">
            <strong>{job.stage}</strong>
            <span>
              {job.status === "completed"
                ? "Your download is ready."
                : job.estimated_seconds_remaining
                  ? `About ${job.estimated_seconds_remaining} second${job.estimated_seconds_remaining === 1 ? "" : "s"} remaining`
                  : "Preparing your document…"}
            </span>
            <b>{job.progress}%</b>
          </div>
          <div
            className="document-progress-track"
            role="progressbar"
            aria-label="Conversion progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={job.progress}
          >
            <span style={{ width: `${job.progress}%` }} />
          </div>
        </div>
      )}

      <div className="document-converter-actions">
        <button type="button" className="btn btn-primary" onClick={convert} disabled={!file || busy}>
          {busy ? "Converting…" : file ? `Convert to ${direction(file).split(" → ")[1]}` : "Choose a document"}
        </button>
        {job?.status === "completed" && token && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void download(job, token).catch((caught) => setError(caught instanceof Error ? caught.message : "Download failed."))}
          >
            Download again
          </button>
        )}
      </div>

      <div className="document-converter-safety">
        <strong>Conversion quality</strong>
        <p>DOCX-to-PDF uses a full office rendering engine for reliable print layout. PDF-to-DOCX reconstructs editable text, images and tables; scanned or unusually complex PDFs can still need manual adjustment.</p>
        <span>Files are isolated during conversion and automatically deleted after the short download window.</span>
      </div>
    </section>
  );
}
