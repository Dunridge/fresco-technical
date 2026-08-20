"""Row classification inside a hardware-set region.

Prose ("PROVIDE EACH SINGLE DOOR TO HAVE THE FOLLOWING:") has to be separated
from data rows *before* column geometry is measured — a full-width sentence
would otherwise bridge every column gap and destroy the column model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median

from ..classification import vocab
from ..detection.sets import is_column_header_line
from ..parsing.layout import Line, Word

MIN_GAP_SPACE_MULTIPLIER = 1.6
MIN_GAP_ABSOLUTE = 4.0
MIN_SEGMENTS_FOR_DATA_ROW = 3


class RowKind(str, Enum):
    COLUMN_HEADER = "column_header"
    DATA = "data"
    TEXT = "text"


@dataclass
class ClassifiedRow:
    line: Line
    kind: RowKind
    segments: int


def estimate_min_gap(lines: list[Line]) -> float:
    widths = [
        (w.x1 - w.x0) / max(len(w.text), 1)
        for line in lines
        for w in line.words
        if w.text
    ]
    char_width = median(widths) if widths else 5.0
    return max(char_width * MIN_GAP_SPACE_MULTIPLIER, MIN_GAP_ABSOLUTE)


def segment_line(line: Line, min_gap: float) -> list[list[Word]]:
    """Split a row into cell-like runs separated by more than one space."""
    if not line.words:
        return []
    groups: list[list[Word]] = [[line.words[0]]]
    for word in line.words[1:]:
        if word.x0 - groups[-1][-1].x1 >= min_gap:
            groups.append([word])
        else:
            groups[-1].append(word)
    return groups


def _starts_with_quantity(line: Line) -> bool:
    first = line.words[0].text.strip().upper() if line.words else ""
    return bool(vocab.PLAIN_INT_RE.match(first)) or vocab.looks_like_unit(first)


def classify_rows(lines: list[Line], min_gap: float) -> list[ClassifiedRow]:
    rows: list[ClassifiedRow] = []
    for line in lines:
        segments = len(segment_line(line, min_gap))
        if is_column_header_line(line):
            kind = RowKind.COLUMN_HEADER
        elif segments >= MIN_SEGMENTS_FOR_DATA_ROW:
            kind = RowKind.DATA
        elif segments >= 2 and _starts_with_quantity(line):
            kind = RowKind.DATA
        else:
            kind = RowKind.TEXT
        rows.append(ClassifiedRow(line=line, kind=kind, segments=segments))
    return rows
