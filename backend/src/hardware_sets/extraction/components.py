"""Turn a classified hardware-set region into schema components."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from ..classification import vocab
from ..classification.columns import Column, cells_for_line, classify_columns, detect_columns, read_header_labels
from ..models import Component, Field_, Span
from ..parsing.layout import Line
from .rows import ClassifiedRow, RowKind, estimate_min_gap, segment_line


@dataclass
class RegionExtraction:
    components: list[Component]
    description_lines: list[Line]
    columns: list[Column]
    header_line: Line | None
    not_used: bool


def extract_region(
    lines: list[Line],
    legend: dict[str, str] | None = None,
    document_hints: dict[int, Field_] | None = None,
    header_line: Line | None = None,
    exclude_span: tuple[float, float] | None = None,
    geometry_lines: list[Line] | None = None,
) -> RegionExtraction:
    min_gap = estimate_min_gap(lines) if lines else 7.0
    rows = classify_rows_for_region(lines, min_gap)

    if header_line is None:
        header_line = next((r.line for r in rows if r.kind is RowKind.COLUMN_HEADER), None)
    data_lines = [r.line for r in rows if r.kind is RowKind.DATA]

    # Geometry comes from the data rows alone. A header's own spacing often
    # differs from the body's - one real schedule prints `QTY. FINISH` close
    # enough together to bridge two columns that the rows keep well apart.
    # In a set-column table every set shares one geometry. Measuring it from a
    # single set's handful of rows gave a different column model per set;
    # measuring once over the whole table keeps field mapping consistent.
    model_lines = geometry_lines if geometry_lines else data_lines
    columns = detect_columns(model_lines) or detect_columns(
        model_lines + ([header_line] if header_line is not None else [])
    )
    if columns:
        read_header_labels(header_line, columns)
        for line in model_lines:
            for column, cell in zip(columns, cells_for_line(line, columns)):
                column.values.append(cell)
        classify_columns(columns, legend=legend, document_hints=document_hints)
        _resolve_mfr_finish_columns(columns)
        _split_manufacturer_product_column(columns)
        _exclude_column(columns, exclude_span)

    components: list[Component] = []
    description_lines: list[Line] = []
    seen_data = False
    previous_line: Line | None = None
    line_height = median([r.line.height for r in rows if r.line.height > 0]) if rows else 12.0

    for row in rows:
        if row.kind is RowKind.COLUMN_HEADER:
            seen_data = True
            previous_line = row.line
            continue
        if row.kind is RowKind.DATA:
            component = _build_component(row.line, columns)
            if component is not None:
                components.append(component)
                seen_data = True
            previous_line = row.line
            continue
        if components and _is_continuation(row.line, previous_line, columns, line_height):
            _attach_continuation(components[-1], row.line, columns)
            previous_line = row.line
            continue
        if not seen_data and not components:
            description_lines.append(row.line)
        # Text after the last component that is not a wrapped cell is document
        # boilerplate (installation notes, general requirements) and is dropped
        # rather than being folded into the preceding component.

    not_used = not components and any(
        vocab.contains_not_used_marker(line.text) or vocab.is_not_used_marker(line.text)
        for line in description_lines
    )
    return RegionExtraction(
        components=components,
        description_lines=description_lines,
        columns=columns,
        header_line=header_line,
        not_used=not_used,
    )


def classify_rows_for_region(lines: list[Line], min_gap: float) -> list[ClassifiedRow]:
    from .rows import classify_rows

    return classify_rows(lines, min_gap)


EXCLUDED_LABEL = "__excluded__"


def _exclude_column(columns: list[Column], span: tuple[float, float] | None) -> None:
    """Keep a non-component column (the set identifier) out of field mapping."""
    if span is None:
        return
    low, high = span
    for column in columns:
        if column.raw_x0 >= low - 2 and column.raw_x1 <= high + 2:
            column.field_ = Field_.UNKNOWN
            column.header_label = EXCLUDED_LABEL
            column.values = ["" for _ in column.values]


MANUFACTURER_PRODUCT_SEPARATOR = " - "


def _split_manufacturer_product_column(columns: list[Column]) -> None:
    """Split a `MANUFACTURER - PRODUCT` column into its two fields.

    Driven by the printed header, not by guessing: only a column whose own
    heading names both parts is split, and only on the separator the heading
    itself uses.
    """
    for column in columns:
        # The merged column may have classified as either half of itself.
        if column.field_ not in (Field_.MFR, Field_.CATALOG_NUMBER):
            continue
        label = (column.header_label or "").upper()
        if not ("MANUFACTURER" in label or "MFR" in label or "MFG" in label):
            continue
        if not any(token in label for token in ("PRODUCT", "CATALOG", "MODEL", "ITEM")):
            continue
        if sum(1 for v in column.filled if MANUFACTURER_PRODUCT_SEPARATOR in v) < max(
            1, len(column.filled) // 2
        ):
            continue
        column.field_ = Field_.MFR
        column.split_target = Field_.CATALOG_NUMBER
        return


def _column_for(columns: list[Column], field_: Field_) -> Column | None:
    return next((c for c in columns if c.field_ is field_), None)


MERGED_PAIR_MIN_RATIO = 0.5
MERGED_PAIR_MIN_CONFIDENCE = 0.6


def _resolve_mfr_finish_columns(columns: list[Column]) -> None:
    """Recover a manufacturer or finish that shares a column with the other.

    Schedules routinely print `MK US26D` in one column. Two cases are handled:
    one of the pair was classified and its cells carry a trailing value of the
    other type, or neither was classified because every cell holds both. In the
    second case the split order is decided by whichever token in each cell is
    *unambiguously* typed, so a column of `PE US26D` resolves PE to the
    manufacturer without PE itself ever being looked up.
    """
    mfr = _column_for(columns, Field_.MFR)
    finish = _column_for(columns, Field_.FINISH)
    if mfr is not None and finish is not None:
        return
    if mfr is None and finish is None:
        _split_combined_column(columns)
        return

    source = mfr or finish
    assert source is not None
    missing_is_finish = finish is None
    predicate = vocab.looks_like_finish if missing_is_finish else vocab.looks_like_manufacturer

    multi = [v for v in source.filled if len(v.split()) >= 2]
    if len(multi) < max(1, len(source.filled) // 2):
        return
    if not all(predicate(v.split()[-1] if missing_is_finish else v.split()[0]) for v in multi):
        return

    source.field_ = Field_.MFR if missing_is_finish else Field_.FINISH
    source.split_target = Field_.FINISH if missing_is_finish else Field_.MFR


def _pair_order_votes(values: list[str]) -> tuple[int, int, int]:
    """Vote on whether two-token cells read `mfr finish` or `finish mfr`."""
    manufacturer_first = 0
    finish_first = 0
    pairs = 0
    for value in values:
        tokens = value.split()
        if len(tokens) != 2:
            continue
        pairs += 1
        head, tail = tokens
        if vocab.looks_like_finish(tail) and not vocab.looks_like_finish(head):
            manufacturer_first += 1
        elif vocab.looks_like_finish(head) and not vocab.looks_like_finish(tail):
            finish_first += 1
        elif vocab.looks_like_manufacturer(head) and not vocab.looks_like_manufacturer(tail):
            manufacturer_first += 1
        elif vocab.looks_like_manufacturer(tail) and not vocab.looks_like_manufacturer(head):
            finish_first += 1
    return manufacturer_first, finish_first, pairs


def _split_combined_column(columns: list[Column]) -> None:
    best: tuple[float, Column, bool] | None = None
    for column in columns:
        if column.field_ in (Field_.QTY, Field_.DESCRIPTION, Field_.CATALOG_NUMBER, Field_.UNIT):
            continue
        filled = column.filled
        if not filled:
            continue
        manufacturer_first, finish_first, pairs = _pair_order_votes(filled)
        if pairs < max(1, int(len(filled) * MERGED_PAIR_MIN_RATIO)):
            continue
        votes = max(manufacturer_first, finish_first)
        confidence = votes / pairs if pairs else 0.0
        if confidence < MERGED_PAIR_MIN_CONFIDENCE:
            continue
        if best is None or confidence > best[0]:
            best = (confidence, column, manufacturer_first >= finish_first)

    if best is None:
        return
    confidence, column, manufacturer_first = best
    column.field_ = Field_.MFR if manufacturer_first else Field_.FINISH
    column.split_target = Field_.FINISH if manufacturer_first else Field_.MFR
    column.score = round(confidence, 3)


def _cell_map(line: Line, columns: list[Column]) -> dict[Field_, str]:
    if not columns:
        return {}
    values: dict[Field_, str] = {}
    for column, cell in zip(columns, cells_for_line(line, columns)):
        text = cell.strip()
        if not text or column.field_ is Field_.UNKNOWN:
            continue
        target = column.split_target
        if (
            target is Field_.CATALOG_NUMBER
            and MANUFACTURER_PRODUCT_SEPARATOR in text
        ):
            manufacturer, _, product = text.partition(MANUFACTURER_PRODUCT_SEPARATOR)
            values[Field_.MFR] = manufacturer.strip()
            values[Field_.CATALOG_NUMBER] = product.strip()
            continue
        if target is not None and len(text.split()) >= 2:
            tokens = text.split()
            if target is Field_.FINISH:
                values[column.field_] = " ".join(tokens[:-1])
                values[Field_.FINISH] = tokens[-1]
            else:
                values[Field_.MFR] = tokens[0]
                values[column.field_] = " ".join(tokens[1:])
            continue
        values[column.field_] = (values.get(column.field_, "") + " " + text).strip()
    return values


def _parse_qty(raw: str | None) -> tuple[int | None, str | None]:
    """Return `(qty, leftover)`. Missing quantities stay `None`, never guessed."""
    if not raw:
        return None, None
    tokens = raw.replace(",", " ").split()
    if not tokens:
        return None, None
    head = tokens[0].strip().upper()
    if vocab.PLAIN_INT_RE.match(head):
        return int(head), " ".join(tokens[1:]) or None
    return None, raw


def _build_component(line: Line, columns: list[Column]) -> Component | None:
    values = _cell_map(line, columns)
    if not values:
        return None

    qty, leftover = _parse_qty(values.get(Field_.QTY))
    description = values.get(Field_.DESCRIPTION)
    if description is None and leftover:
        description = leftover

    if description is None and not any(
        values.get(f) for f in (Field_.CATALOG_NUMBER, Field_.MFR, Field_.FINISH)
    ):
        return None

    # A description that still carries its own leading count, e.g. "3 HINGES".
    if qty is None and description:
        parsed, rest = _parse_qty(description)
        if parsed is not None and rest and _column_for(columns, Field_.QTY) is None:
            qty, description = parsed, rest

    component = Component(
        qty=qty,
        description=_clean(description),
        catalog_number=_clean(values.get(Field_.CATALOG_NUMBER)),
        mfr=_clean(values.get(Field_.MFR)),
        finish=_clean(values.get(Field_.FINISH)),
        notes=_clean(values.get(Field_.NOTES)),
        location=Span(page=line.page, bbox=line.bbox, line_range=[line.index, line.index]),
    )
    component.confidence = _component_confidence(component, columns)
    return component


CONTINUATION_LINE_GAP = 2.0
CONTINUATION_X_TOLERANCE = 3.0


def _is_continuation(
    line: Line, previous: Line | None, columns: list[Column], line_height: float
) -> bool:
    """A wrapped cell sits under its column and directly under its own row."""
    description = _column_for(columns, Field_.DESCRIPTION)
    if description is None:
        return False
    if line.x0 < description.raw_x0 - CONTINUATION_X_TOLERANCE:
        return False
    if previous is not None and line.y0 - previous.y1 > line_height * CONTINUATION_LINE_GAP:
        return False
    return True


def _attach_continuation(component: Component, line: Line, columns: list[Column]) -> None:
    """Wrapped description text belongs to the component above it."""
    text = line.text.strip()
    if not text:
        return
    description_column = _column_for(columns, Field_.DESCRIPTION)
    notes_column = _column_for(columns, Field_.NOTES)

    target = "description"
    if notes_column is not None and line.x0 >= notes_column.x0:
        target = "notes"
    elif description_column is not None and line.x0 < description_column.x0 - 2:
        target = "notes" if component.notes else "description"

    current = getattr(component, target)
    setattr(component, target, f"{current} {text}".strip() if current else text)
    if component.location is not None:
        component.location.bbox = [
            min(component.location.bbox[0], line.x0),
            min(component.location.bbox[1], line.y0),
            max(component.location.bbox[2], line.x1),
            max(component.location.bbox[3], line.y1),
        ]
        component.location.line_range = [component.location.line_range[0], line.index]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip(" .,;:-")
    return cleaned or None


FIELD_VALIDATORS = {
    "catalog_number": vocab.looks_like_catalog_number,
    "mfr": vocab.looks_like_manufacturer,
    "finish": vocab.looks_like_finish,
}


def _component_confidence(component: Component, columns: list[Column]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name in ("qty", "description", "catalog_number", "mfr", "finish", "notes"):
        value = getattr(component, name)
        if value is None:
            continue
        column = _column_for(columns, Field_(name)) if name in Field_._value2member_map_ else None
        base = column.score if column is not None else 0.5
        validator = FIELD_VALIDATORS.get(name)
        if validator is not None and isinstance(value, str):
            if validator(value):
                base = min(base + 0.2, 1.0)
            elif vocab.is_ambiguous_code(value):
                # Resolved purely from column context: correct, but worth flagging.
                base = min(base, 0.75)
            else:
                base = max(base - 0.2, 0.1)
        scores[name] = round(min(max(base, 0.05), 1.0), 3)
    return scores
