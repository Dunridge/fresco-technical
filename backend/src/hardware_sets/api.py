"""HTTP API backing the review UI.

Deliberately small: upload a PDF, read the extraction, render a page image so
the UI can draw the bounding boxes, and store reviewer corrections as JSON.
There is no database - corrections are a flat file per document, which is all
the feedback feature needs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .models import ExtractionResult, HardwareSet
from .parsing.pdf import render_page_png
from .pipeline import extract_hardware_sets

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
DOCUMENT_ID_RE = re.compile(r"^[0-9a-f]{32}$")

STORAGE_ROOT = Path(os.environ.get("HARDWARE_SETS_STORAGE", Path(tempfile.gettempdir()) / "hardware-sets"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        # Next.js falls back to the next free port when 3000 is taken, so the
        # nearby ports are allowed by default too.
        "HARDWARE_SETS_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:3100,http://127.0.0.1:3100",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="Hardware Set Extractor", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class ExtractionResponse(BaseModel):
    document_id: str
    filename: str
    result: ExtractionResult


class FeedbackPayload(BaseModel):
    hardware_sets: list[HardwareSet] = Field(default_factory=list)
    note: str | None = None
    # Set numbers the reviewer actually opened. A golden may only be built from
    # these - see evals/golden_from_review.py.
    reviewed_set_numbers: list[str] = Field(default_factory=list)


def _document_dir(document_id: str) -> Path:
    if not DOCUMENT_ID_RE.match(document_id):
        raise HTTPException(status_code=400, detail="Malformed document id.")
    directory = STORAGE_ROOT / document_id
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail="Unknown document.")
    return directory


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractionResponse)
async def extract(file: UploadFile = File(...), llm: bool = False) -> ExtractionResponse:
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 50 MB.")
    if not payload.startswith(PDF_MAGIC):
        raise HTTPException(status_code=415, detail="That file is not a PDF.")

    document_id = uuid.uuid4().hex
    directory = STORAGE_ROOT / document_id
    directory.mkdir(parents=True, exist_ok=True)
    pdf_path = directory / "source.pdf"
    pdf_path.write_bytes(payload)

    try:
        result = extract_hardware_sets(pdf_path, use_llm=llm)
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Could not read that PDF: {exc}") from exc

    result.source = file.filename or "upload.pdf"
    (directory / "result.json").write_text(json.dumps(result.model_dump(mode="json"), indent=2))
    (directory / "filename.txt").write_text(result.source)
    return ExtractionResponse(document_id=document_id, filename=result.source, result=result)


@app.get("/documents/{document_id}", response_model=ExtractionResponse)
def get_document(document_id: str) -> ExtractionResponse:
    directory = _document_dir(document_id)
    result = ExtractionResult.model_validate_json((directory / "result.json").read_text())
    filename_path = directory / "filename.txt"
    return ExtractionResponse(
        document_id=document_id,
        filename=filename_path.read_text() if filename_path.exists() else result.source,
        result=result,
    )


@app.get("/documents/{document_id}/pages/{page}.png")
def page_image(document_id: str, page: int, scale: float = 2.0) -> Response:
    directory = _document_dir(document_id)
    try:
        png = render_page_png(directory / "source.pdf", page, scale=max(0.5, min(scale, 4.0)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.post("/documents/{document_id}/feedback")
def save_feedback(document_id: str, payload: FeedbackPayload) -> dict[str, object]:
    directory = _document_dir(document_id)
    (directory / "feedback.json").write_text(json.dumps(payload.model_dump(mode="json"), indent=2))
    return {"saved": True, "hardware_sets": len(payload.hardware_sets)}


@app.get("/documents/{document_id}/feedback")
def load_feedback(document_id: str) -> FeedbackPayload:
    directory = _document_dir(document_id)
    path = directory / "feedback.json"
    if not path.exists():
        return FeedbackPayload()
    return FeedbackPayload.model_validate_json(path.read_text())


@app.delete("/documents/{document_id}")
def delete_document(document_id: str) -> dict[str, bool]:
    shutil.rmtree(_document_dir(document_id), ignore_errors=True)
    return {"deleted": True}
