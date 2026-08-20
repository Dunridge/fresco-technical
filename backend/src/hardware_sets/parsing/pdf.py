"""PDF text + geometry extraction.

Two backends are available so the choice can be re-measured rather than
assumed; see `evals/parser_comparison.py` and the decision log in PLAN.md.
"""

from __future__ import annotations

from pathlib import Path

from .layout import Document, Page, Word, group_words_into_lines

MIN_WORDS_FOR_TEXT_PAGE = 5


def parse_pdf(path: str | Path, backend: str = "pymupdf") -> Document:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such PDF: {path}")
    if backend == "pymupdf":
        return _parse_pymupdf(path)
    if backend == "pdfplumber":
        return _parse_pdfplumber(path)
    raise ValueError(f"Unknown PDF backend: {backend!r}")


def _parse_pymupdf(path: Path) -> Document:
    import pymupdf

    document = Document(source=str(path))
    with pymupdf.open(path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            raw = page.get_text("words")
            words = [
                Word(text=w[4], x0=float(w[0]), y0=float(w[1]), x1=float(w[2]), y1=float(w[3]))
                for w in raw
                if w[4].strip()
            ]
            document.pages.append(
                Page(
                    number=page_index,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    lines=group_words_into_lines(words, page_index),
                    has_text=len(words) >= MIN_WORDS_FOR_TEXT_PAGE,
                )
            )
    return document


def _parse_pdfplumber(path: Path) -> Document:
    import pdfplumber

    document = Document(source=str(path))
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = [
                Word(
                    text=w["text"],
                    x0=float(w["x0"]),
                    y0=float(w["top"]),
                    x1=float(w["x1"]),
                    y1=float(w["bottom"]),
                )
                for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)
                if w["text"].strip()
            ]
            document.pages.append(
                Page(
                    number=page_index,
                    width=float(page.width),
                    height=float(page.height),
                    lines=group_words_into_lines(words, page_index),
                    has_text=len(words) >= MIN_WORDS_FOR_TEXT_PAGE,
                )
            )
    return document


def render_page_png(path: str | Path, page_number: int, scale: float = 2.0) -> bytes:
    """Rasterise one page. Used by the API so the UI can draw bounding boxes."""
    import pymupdf

    with pymupdf.open(path) as pdf:
        if not 1 <= page_number <= pdf.page_count:
            raise ValueError(f"Page {page_number} out of range (1-{pdf.page_count})")
        page = pdf[page_number - 1]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        return pixmap.tobytes("png")
