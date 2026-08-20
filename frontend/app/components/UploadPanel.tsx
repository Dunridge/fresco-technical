"use client";

import { useRef, useState } from "react";

import { useExtraction } from "@/context/ExtractionContext";

export function UploadPanel() {
  const { status, filename, result, upload, clear } = useExtraction();
  const [useLlm, setUseLlm] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const busy = status === "uploading";

  const handleFile = (file: File | undefined) => {
    if (file) void upload(file, useLlm);
  };

  return (
    <section
      className={`upload ${dragging ? "upload--dragging" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        handleFile(event.dataTransfer.files?.[0]);
      }}
    >
      <div className="upload__main">
        <h2>Specification PDF</h2>
        {result ? (
          <p className="upload__file">
            <strong>{filename}</strong> — {result.hardware_sets.length} hardware sets across{" "}
            {result.page_count} {result.page_count === 1 ? "page" : "pages"}
          </p>
        ) : (
          <p className="muted">Drop a Division 08 specbook here, or choose a file.</p>
        )}
      </div>

      <div className="upload__actions">
        <label className="checkbox" title="Revisits low-confidence sets with an LLM. Needs ANTHROPIC_API_KEY on the API.">
          <input
            type="checkbox"
            checked={useLlm}
            disabled={busy}
            onChange={(event) => setUseLlm(event.target.checked)}
          />
          LLM assist
        </label>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(event) => handleFile(event.target.files?.[0])}
        />
        <button type="button" onClick={() => inputRef.current?.click()} disabled={busy}>
          {busy ? "Extracting…" : result ? "Choose another" : "Choose PDF"}
        </button>
        {result && (
          <button type="button" className="ghost" onClick={clear} disabled={busy}>
            Clear
          </button>
        )}
      </div>
    </section>
  );
}
