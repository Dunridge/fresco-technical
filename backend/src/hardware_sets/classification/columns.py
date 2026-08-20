"""Column geometry detection and column -> field classification.

Two stages:

1. `detect_columns` recovers column boundaries from word geometry. A boundary
   is an x-range that *no word on any row* occupies, wider than a space. That
   union-gap test works for both ruled table schedules and plain indented
   lists, so one code path handles both layout families.

2. `classify_columns` decides which component field each column carries. It
   scores a column from the aggregate of its values, never from a single cell,
   and drops codes that are ambiguous between manufacturer and finish out of
   the scoring entirely so the column's unambiguous members decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from ..models import Field_
from ..parsing.layout import Line, Word
from . import vocab

MIN_GAP_SPACE_MULTIPLIER = 1.6
MIN_GAP_ABSOLUTE = 4.0
# Share of rows allowed to overflow a separator before it stops being one. A
# strict union works for a short region, but over hundreds of rows a single
# long cell that spills into its neighbour would erase the boundary for every
# other row. Small regions round this to zero, keeping the strict behaviour.
COLUMN_OVERFLOW_TOLERANCE = 0.08
BIN_WIDTH = 1.0
FIELD_SCORE_FLOOR = 0.34
HEADER_BONUS = 0.55

HEADER_LABELS: dict[str, Field_] = {
    "QTY": Field_.QTY, "QTY.": Field_.QTY, "QUANTITY": Field_.QTY, "NO": Field_.QTY,
    "NO.": Field_.QTY, "#": Field_.QTY, "AMT": Field_.QTY, "COUNT": Field_.QTY,
    "UNIT": Field_.UNIT, "U/M": Field_.UNIT, "UOM": Field_.UNIT, "EA": Field_.UNIT,
    "DESCRIPTION": Field_.DESCRIPTION, "ITEM": Field_.DESCRIPTION,
    "HARDWARE": Field_.DESCRIPTION, "COMPONENT": Field_.DESCRIPTION,
    "ITEMS": Field_.DESCRIPTION, "TYPE": Field_.DESCRIPTION,
    "CATALOG": Field_.CATALOG_NUMBER, "CATALOG NUMBER": Field_.CATALOG_NUMBER,
    "CATALOG NO": Field_.CATALOG_NUMBER, "CATALOG NO.": Field_.CATALOG_NUMBER,
    "CAT NO": Field_.CATALOG_NUMBER, "CAT. NO.": Field_.CATALOG_NUMBER,
    "PRODUCT": Field_.CATALOG_NUMBER, "PRODUCT NO": Field_.CATALOG_NUMBER,
    "PRODUCT NUMBER": Field_.CATALOG_NUMBER, "MODEL": Field_.CATALOG_NUMBER,
    "MODEL NO": Field_.CATALOG_NUMBER, "PART NUMBER": Field_.CATALOG_NUMBER,
    "MFR": Field_.MFR, "MFR.": Field_.MFR, "MFG": Field_.MFR, "MFG.": Field_.MFR,
    "MANUFACTURER": Field_.MFR, "MANF": Field_.MFR, "MAKE": Field_.MFR,
    "FINISH": Field_.FINISH, "FIN": Field_.FINISH, "FIN.": Field_.FINISH,
    "FINISHES": Field_.FINISH,
    "NOTES": Field_.NOTES, "NOTE": Field_.NOTES, "REMARKS": Field_.NOTES,
    "COMMENTS": Field_.NOTES, "REMARK": Field_.NOTES,
}


@dataclass
class Column:
    index: int
    x0: float
    x1: float
    raw_x0: float = 0.0
    raw_x1: float = 0.0
    values: list[str] = field(default_factory=list)
    field_: Field_ = Field_.UNKNOWN
    score: float = 0.0
    header_label: str | None = None
    split_target: Field_ | None = None

    def contains(self, word: Word) -> bool:
        return self.x0 <= word.cx <= self.x1

    @property
    def filled(self) -> list[str]:
        return [v for v in self.values if v.strip()]


def _estimate_space_width(lines: list[Line]) -> float:
    widths: list[float] = []
    for line in lines:
        for word in line.words:
            if word.text:
                widths.append((word.x1 - word.x0) / max(len(word.text), 1))
    return median(widths) if widths else 5.0


def detect_columns(lines: list[Line]) -> list[Column]:
    """Recover column intervals from where words sit across rows."""
    words = [w for line in lines for w in line.words]
    if not words:
        return []

    space_width = _estimate_space_width(lines)
    min_gap = max(space_width * MIN_GAP_SPACE_MULTIPLIER, MIN_GAP_ABSOLUTE)
    tolerance = int(len(lines) * COLUMN_OVERFLOW_TOLERANCE)

    merged = (
        _merge_by_union(words, min_gap)
        if tolerance <= 0
        else _merge_by_occupancy(lines, words, min_gap, tolerance)
    )
    if not merged:
        return []

    columns: list[Column] = []
    for index, (x0, x1) in enumerate(merged):
        left = x0 - min_gap / 2 if index else float("-inf")
        right = x1 + min_gap / 2 if index < len(merged) - 1 else float("inf")
        columns.append(Column(index=index, x0=left, x1=right, raw_x0=x0, raw_x1=x1))
    return columns


def _merge_by_union(words: list[Word], min_gap: float) -> list[list[float]]:
    intervals = sorted((w.x0, w.x1) for w in words)
    merged: list[list[float]] = [list(intervals[0])]
    for x0, x1 in intervals[1:]:
        if x0 - merged[-1][1] < min_gap:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    return merged


def _merge_by_occupancy(
    lines: list[Line], words: list[Word], min_gap: float, tolerance: int
) -> list[list[float]]:
    """Treat an x-range as a separator when few enough rows cross it."""
    left = min(w.x0 for w in words)
    right = max(w.x1 for w in words)
    bin_count = max(int((right - left) / BIN_WIDTH) + 1, 1)
    crossings = [0] * bin_count

    for line in lines:
        touched: set[int] = set()
        for word in line.words:
            start = max(int((word.x0 - left) / BIN_WIDTH), 0)
            end = min(int((word.x1 - left) / BIN_WIDTH), bin_count - 1)
            touched.update(range(start, end + 1))
        for index in touched:
            crossings[index] += 1

    spans: list[list[float]] = []
    run_start: int | None = None
    for index, count in enumerate(crossings):
        occupied = count > tolerance
        if occupied and run_start is None:
            run_start = index
        elif not occupied and run_start is not None:
            gap_width = _clear_run_width(crossings, index, tolerance)
            if gap_width >= min_gap:
                spans.append([left + run_start * BIN_WIDTH, left + index * BIN_WIDTH])
                run_start = None
    if run_start is not None:
        spans.append([left + run_start * BIN_WIDTH, right])
    return spans or _merge_by_union(words, min_gap)


def _clear_run_width(crossings: list[int], start: int, tolerance: int) -> float:
    index = start
    while index < len(crossings) and crossings[index] <= tolerance:
        index += 1
    return (index - start) * BIN_WIDTH


def cells_for_line(line: Line, columns: list[Column]) -> list[str]:
    """Bucket a row's words into the detected columns."""
    buckets: list[list[Word]] = [[] for _ in columns]
    for word in line.words:
        target = next((c for c in columns if c.contains(word)), None)
        if target is None:
            target = min(columns, key=lambda c: min(abs(word.cx - c.x0), abs(word.cx - c.x1)))
        buckets[target.index].append(word)
    return [" ".join(w.text for w in sorted(b, key=lambda w: w.x0)) for b in buckets]


def _ratio(values: list[str], predicate) -> float:
    considered = [v for v in values if v.strip()]
    if not considered:
        return 0.0
    return sum(1 for v in considered if predicate(v)) / len(considered)


def _mfr_finish_ratio(values: list[str], predicate) -> float:
    """Score manufacturer/finish using only unambiguous members of the column."""
    considered = [
        v for v in values if v.strip() and not vocab.is_ambiguous_code(v) and len(v.split()) == 1
    ]
    if not considered:
        return 0.0
    return sum(1 for v in considered if predicate(v)) / len(considered)


def _qty_score(values: list[str]) -> float:
    def is_qty(value: str) -> bool:
        token = value.strip().upper().split()[0] if value.split() else ""
        return bool(vocab.PLAIN_INT_RE.match(token)) and 0 < int(token) <= 999
    return _ratio(values, is_qty)


def _description_score(values: list[str]) -> float:
    filled = [v for v in values if v.strip()]
    if not filled:
        return 0.0
    alpha = _ratio(filled, lambda v: sum(ch.isalpha() for ch in v) >= max(3, len(v) * 0.6))
    nouns = sum(
        1 for v in filled if any(tok.strip(".,()") in vocab.HARDWARE_NOUNS for tok in v.upper().split())
    ) / len(filled)
    length = min(sum(len(v) for v in filled) / len(filled) / 14.0, 1.0)
    return min(alpha * 0.45 + nouns * 0.4 + length * 0.15, 1.0)


def _notes_score(values: list[str]) -> float:
    filled = [v for v in values if v.strip()]
    if not filled:
        # A column with nothing in it scores zero, and must not reach the
        # per-value average below - that divided by zero on real documents.
        return 0.0
    if len(filled) == len(values):
        # A fully populated column is a data column, not a remarks column.
        sparsity = 0.0
    else:
        sparsity = 1.0 - len(filled) / len(values)
    words = sum(
        1 for v in filled if any(tok.strip(".,()") in vocab.NOTE_WORDS for tok in v.upper().split())
    ) / len(filled)
    return min(sparsity * 0.45 + words * 0.55, 1.0)


SCORERS = {
    Field_.QTY: _qty_score,
    Field_.UNIT: lambda vs: _ratio(vs, vocab.looks_like_unit),
    Field_.DESCRIPTION: _description_score,
    Field_.CATALOG_NUMBER: lambda vs: _ratio(vs, vocab.looks_like_catalog_number),
    Field_.MFR: lambda vs: _mfr_finish_ratio(vs, vocab.looks_like_manufacturer),
    Field_.FINISH: lambda vs: _mfr_finish_ratio(vs, vocab.looks_like_finish),
    Field_.NOTES: _notes_score,
}

SINGLE_USE_FIELDS = {
    Field_.QTY, Field_.UNIT, Field_.DESCRIPTION, Field_.CATALOG_NUMBER,
    Field_.MFR, Field_.FINISH, Field_.NOTES,
}


def read_header_labels(header_line: Line | None, columns: list[Column]) -> None:
    if header_line is None:
        return
    for column, text in zip(columns, cells_for_line(header_line, columns)):
        column.header_label = text.strip().upper() or None


def _header_field(column: Column) -> Field_ | None:
    if not column.header_label:
        return None
    label = column.header_label.strip().upper().rstrip(":")
    if label in HEADER_LABELS:
        return HEADER_LABELS[label]
    for key, value in HEADER_LABELS.items():
        if len(key) > 3 and label.startswith(key):
            return value
    return None


def classify_columns(
    columns: list[Column],
    legend: dict[str, str] | None = None,
    document_hints: dict[int, Field_] | None = None,
) -> list[Column]:
    """Assign a component field to each column using aggregate column evidence."""
    legend = legend or {}
    candidates: list[tuple[float, int, Field_]] = []

    for column in columns:
        values = column.values
        header_field = _header_field(column)
        for field_, scorer in SCORERS.items():
            score = scorer(values)
            if field_ in (Field_.MFR, Field_.FINISH):
                score = max(score, _legend_score(values, legend, field_))
            if header_field is field_:
                score += HEADER_BONUS
            if score > 0:
                candidates.append((score, column.index, field_))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    taken_columns: set[int] = set()
    taken_fields: set[Field_] = set()

    for score, column_index, field_ in candidates:
        if column_index in taken_columns or field_ in taken_fields:
            continue
        if score < FIELD_SCORE_FLOOR:
            continue
        column = columns[column_index]
        column.field_ = field_
        column.score = min(score, 1.0)
        taken_columns.add(column_index)
        if field_ in SINGLE_USE_FIELDS:
            taken_fields.add(field_)

    _apply_document_hints(columns, document_hints or {})
    _absorb_unknown_columns(columns)
    return columns


def _legend_score(values: list[str], legend: dict[str, str], field_: Field_) -> float:
    """A page legend such as `PE = PEMKO` is direct evidence for that document."""
    if not legend:
        return 0.0
    filled = [vocab.normalize_code(v) for v in values if v.strip()]
    hits = [code for code in filled if code in legend]
    if not hits:
        return 0.0
    if field_ is Field_.MFR:
        matched = sum(1 for code in hits if _legend_value_is_manufacturer(legend[code]))
    else:
        matched = sum(1 for code in hits if not _legend_value_is_manufacturer(legend[code]))
    return matched / len(filled)


def _legend_value_is_manufacturer(value: str) -> bool:
    upper = value.strip().upper()
    if upper in vocab.MANUFACTURER_NAMES:
        return True
    return not vocab.looks_like_finish(upper) and any(
        name in upper or upper in name for name in vocab.MANUFACTURER_NAMES
    )


def _apply_document_hints(columns: list[Column], hints: dict[int, Field_]) -> None:
    """Fall back to document-level column roles when a set has no local evidence.

    A set whose manufacturer column happens to contain only ambiguous codes gets
    resolved by what the same column position carries elsewhere in the document.
    """
    used = {c.field_ for c in columns if c.field_ is not Field_.UNKNOWN}
    for column in columns:
        if column.field_ is not Field_.UNKNOWN:
            continue
        hint = _lookup_hint(hints, column.raw_x0)
        if hint and hint not in used and column.filled:
            column.field_ = hint
            column.score = 0.4
            used.add(hint)


HINT_X_TOLERANCE = 8.0


def _lookup_hint(hints: dict[int, Field_], x0: float) -> Field_ | None:
    best: Field_ | None = None
    best_distance = HINT_X_TOLERANCE
    for key, value in hints.items():
        distance = abs(key - x0)
        if distance <= best_distance:
            best, best_distance = value, distance
    return best


def _absorb_unknown_columns(columns: list[Column]) -> None:
    """Unclassified text columns become description/notes rather than vanishing."""
    described = next((c for c in columns if c.field_ is Field_.DESCRIPTION), None)
    for column in columns:
        if column.field_ is not Field_.UNKNOWN or not column.filled:
            continue
        if described is not None and column.x0 > described.x0:
            column.field_ = Field_.NOTES if not any(
                c.field_ is Field_.NOTES for c in columns
            ) else Field_.UNKNOWN
        elif described is None:
            column.field_ = Field_.DESCRIPTION
            described = column
