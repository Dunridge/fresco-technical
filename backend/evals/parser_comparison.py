"""Milestone 1 experiment: compare the two candidate PDF parsers.

Measures the things the pipeline actually depends on: word coverage, whether
words carry usable geometry, how faithfully visual rows are recovered, and
runtime.

Run:  python evals/parser_comparison.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hardware_sets.parsing.pdf import parse_pdf  # noqa: E402

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.pdf"))


def profile(backend: str, path: Path) -> dict[str, float | int]:
    start = time.perf_counter()
    doc = parse_pdf(path, backend=backend)
    elapsed = time.perf_counter() - start

    words = sum(len(ln.words) for p in doc.pages for ln in p.lines)
    lines = sum(len(p.content_lines) for p in doc.pages)
    zero_area = sum(
        1
        for p in doc.pages
        for ln in p.lines
        for w in ln.words
        if (w.x1 - w.x0) <= 0 or (w.y1 - w.y0) <= 0
    )
    # A hardware row should stay on one line; count rows that kept >= 4 words.
    wide_rows = sum(1 for p in doc.pages for ln in p.lines if len(ln.words) >= 4)
    return {
        "pages": len(doc.pages),
        "words": words,
        "lines": lines,
        "zero_area_words": zero_area,
        "multi_column_rows": wide_rows,
        "seconds": round(elapsed, 4),
    }


def main() -> None:
    for path in FIXTURES:
        print(f"\n=== {path.name} ===")
        for backend in ("pymupdf", "pdfplumber"):
            try:
                stats = profile(backend, path)
            except Exception as exc:  # pragma: no cover - diagnostic script
                print(f"{backend:12s} FAILED: {exc}")
                continue
            print(f"{backend:12s} " + "  ".join(f"{k}={v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
