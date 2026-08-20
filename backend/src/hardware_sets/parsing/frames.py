"""Running header / footer detection.

Page furniture (project name, section number, page number) sits inside a set's
region whenever that set crosses a page break, so it has to be removed before
component rows are extracted. Lines are only dropped when they repeat across
pages *at the same vertical position*, which keeps genuine content that merely
happens to sit near a page edge.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..detection.sets import match_set_header
from .layout import Document, Line

EDGE_FRACTION = 0.15
Y_TOLERANCE_FRACTION = 0.02
MIN_PAGES = 2


def _normalize(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip().upper())
    return re.sub(r"\d+", "#", collapsed)


def _in_edge_zone(line: Line, page_height: float) -> bool:
    margin = page_height * EDGE_FRACTION
    return line.y0 <= margin or line.y1 >= page_height - margin


def detect_frame_lines(document: Document) -> set[tuple[int, int]]:
    """Return `(page, line_index)` pairs that are running headers or footers."""
    if len(document.pages) < MIN_PAGES:
        return set()

    buckets: dict[str, list[tuple[int, int, float]]] = defaultdict(list)
    for page in document.pages:
        for line in page.content_lines:
            if not _in_edge_zone(line, page.height):
                continue
            if match_set_header(line) is not None:
                continue
            buckets[_normalize(line.text)].append((page.number, line.index, line.y0))

    frames: set[tuple[int, int]] = set()
    tolerance = max(p.height for p in document.pages) * Y_TOLERANCE_FRACTION
    for occurrences in buckets.values():
        pages = {page for page, _, _ in occurrences}
        if len(pages) < MIN_PAGES:
            continue
        anchor = occurrences[0][2]
        aligned = [o for o in occurrences if abs(o[2] - anchor) <= tolerance]
        if len({page for page, _, _ in aligned}) < MIN_PAGES:
            continue
        for page, index, _ in aligned:
            frames.add((page, index))
    return frames
