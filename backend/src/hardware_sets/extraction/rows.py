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
from ..parsing.layout import (
    MIN_SEGMENTS_FOR_DATA_ROW,
    Line,
    Word,
    estimate_min_gap,
    segment_line,
)

__all__ = [
    "ClassifiedRow",
    "RowKind",
    "classify_rows",
    "estimate_min_gap",
    "segment_line",
]


class RowKind(str, Enum):
    COLUMN_HEADER = "column_header"
    DATA = "data"
    TEXT = "text"


@dataclass
class ClassifiedRow:
    line: Line
    kind: RowKind
    segments: int


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
