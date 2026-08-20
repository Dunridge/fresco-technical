"""Layout primitives shared by every stage of the pipeline.

The pipeline deliberately keeps words, bounding boxes and reading order alive
all the way to field extraction: column position is the main evidence used to
tell a manufacturer column from a finish column.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Line:
    page: int
    index: int
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.x1 for w in self.words)

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.y1 for w in self.words)

    @property
    def bbox(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def is_blank(self) -> bool:
        return not self.text.strip()


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    has_text: bool = True

    @property
    def content_lines(self) -> list[Line]:
        return [ln for ln in self.lines if not ln.is_blank()]


@dataclass
class Document:
    source: str
    pages: list[Page] = field(default_factory=list)

    def line_at(self, page: int, index: int) -> Line | None:
        for p in self.pages:
            if p.number == page:
                for ln in p.lines:
                    if ln.index == index:
                        return ln
        return None


def group_words_into_lines(words: list[Word], page_number: int) -> list[Line]:
    """Cluster words into visual rows.

    PDF text extractors report their own line grouping, but in tabular
    schedules a single visual row is frequently split across several blocks.
    Clustering on the vertical centre recovers the row the human eye sees.
    """
    if not words:
        return []

    heights = [w.y1 - w.y0 for w in words if w.y1 > w.y0]
    tolerance = (median(heights) if heights else 8.0) * 0.6

    ordered = sorted(words, key=lambda w: (w.cy, w.x0))
    rows: list[list[Word]] = [[ordered[0]]]
    for word in ordered[1:]:
        current = rows[-1]
        row_cy = sum(w.cy for w in current) / len(current)
        if abs(word.cy - row_cy) <= tolerance:
            current.append(word)
        else:
            rows.append([word])

    lines: list[Line] = []
    for i, row in enumerate(sorted(rows, key=lambda r: min(w.y0 for w in r))):
        lines.append(Line(page=page_number, index=i, words=sorted(row, key=lambda w: w.x0)))
    return lines


MIN_GAP_SPACE_MULTIPLIER = 1.6
MIN_GAP_ABSOLUTE = 4.0
MIN_SEGMENTS_FOR_DATA_ROW = 3


def estimate_min_gap(lines: list[Line]) -> float:
    """The x-gap that separates two cells rather than two words in one cell."""
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


def looks_like_data_row(line: Line, min_gap: float) -> bool:
    """A row carrying several distinct cells - a component, not page furniture."""
    segments = len(segment_line(line, min_gap))
    if segments >= MIN_SEGMENTS_FOR_DATA_ROW:
        return True
    first = line.words[0].text.strip().rstrip(".") if line.words else ""
    return segments >= 2 and first.isdigit()


def bbox_union(boxes: list[list[float]]) -> list[float]:
    xs0 = [b[0] for b in boxes]
    ys0 = [b[1] for b in boxes]
    xs1 = [b[2] for b in boxes]
    ys1 = [b[3] for b in boxes]
    return [min(xs0), min(ys0), max(xs1), max(ys1)]
