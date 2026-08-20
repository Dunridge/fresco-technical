"""Detection for schedules where the set identifier is a *column*, not a header.

Most specbooks announce a set on its own line (`HARDWARE SET NO. 1`) and list
its components underneath. A second family instead prints one continuous table
whose leftmost column carries the set identifier:

    SET   HARDWARE TYPE    MANUFACTURER - PRODUCT      QTY  FINISH
    1.1   CYLINDER / CORE  SCHLAGE - FSIC PRIMUS        1   613
    1.2   MORTISE HINGE    IVES - 5BB1 4.5" x 4.5"      3   613
          MORTISE LOCKSET  SCHLAGE - L9077              1   613

Here a set begins wherever the set column changes, which is the "subtle set
number change" boundary the challenge calls out. Rows with an empty set cell -
or with wrapped door-description text in it - continue the set above.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..classification.columns import cells_for_line, detect_columns
from ..parsing.layout import Line
from .sets import is_region_end, normalize_set_number

SET_COLUMN_LABELS = {"SET", "SETS", "SET NO", "SET NO.", "SET #", "HW SET", "HDW SET", "GROUP"}
SET_ID_RE = re.compile(r"^\d{1,3}(?:[.\-]\d{1,3})?[A-Z]{0,2}$")
MIN_ROWS_FOR_TABLE = 3
MIN_DISTINCT_SET_IDS = 2


@dataclass
class ColumnSetRegion:
    """One set discovered in a set-column table."""

    set_number: str
    header_line: Line
    lines: list[Line] = field(default_factory=list)
    # x-range of the set-identifier column, which is not a component field.
    set_column_span: tuple[float, float] = (0.0, 0.0)
    # Every row of the table this set belongs to, so all sets in one table
    # share a single column model.
    table_lines: list[Line] = field(default_factory=list)

    @property
    def pages(self) -> list[int]:
        seen: list[int] = []
        for line in self.lines:
            if line.page not in seen:
                seen.append(line.page)
        return seen


def _looks_like_set_column_header(line: Line) -> int | None:
    """Return the index of the `SET` cell when this row heads a set-column table."""
    columns = detect_columns([line])
    if len(columns) < 3:
        return None
    cells = [c.strip().upper().rstrip(".:") for c in cells_for_line(line, columns)]
    for index, cell in enumerate(cells):
        if cell in SET_COLUMN_LABELS or cell.replace(" ", "") in {"SETNO", "SET#"}:
            # A `SET` cell alone is not enough - the row must also name the
            # component fields, or any sentence starting with "Set" qualifies.
            others = {c for i, c in enumerate(cells) if i != index and c}
            if others & {
                "QTY", "QTY.", "QUANTITY", "DESCRIPTION", "HARDWARE", "HARDWARE TYPE",
                "ITEM", "MANUFACTURER", "MFR", "MFG", "FINISH", "FIN", "NOTES",
                "REMARKS", "PRODUCT", "CATALOG", "TYPE",
            }:
                return index
    return None


def find_column_set_regions(stream: list[Line]) -> list[ColumnSetRegion]:
    """Split a set-column schedule into one region per set identifier."""
    regions: list[ColumnSetRegion] = []
    index = 0
    while index < len(stream):
        set_column = _looks_like_set_column_header(stream[index])
        if set_column is None:
            index += 1
            continue
        header_line = stream[index]
        body, index = _collect_table_body(stream, index + 1)
        regions.extend(_split_body_by_set_id(body, header_line, set_column))
    return regions


def _collect_table_body(stream: list[Line], start: int) -> tuple[list[Line], int]:
    body: list[Line] = []
    index = start
    while index < len(stream):
        line = stream[index]
        if is_region_end(line):
            break
        if _looks_like_set_column_header(line) is not None:
            # A repeated header on the next page continues the same table.
            index += 1
            continue
        body.append(line)
        index += 1
    return body, index


def _split_body_by_set_id(
    body: list[Line], header_line: Line, set_column: int
) -> list[ColumnSetRegion]:
    if len(body) < MIN_ROWS_FOR_TABLE:
        return []

    # Column geometry is measured from the body plus its header, so the set
    # column's x-range reflects the rows, not just the heading.
    columns = detect_columns([header_line, *body])
    if set_column >= len(columns):
        columns = detect_columns([header_line])
        if set_column >= len(columns):
            return []
    boundary = columns[set_column]

    regions: list[ColumnSetRegion] = []
    for line in body:
        cell = " ".join(
            word.text for word in line.words if boundary.x0 <= word.cx <= boundary.x1
        ).strip()
        token = cell.split()[0].rstrip(".:") if cell else ""
        if SET_ID_RE.match(token.upper()):
            regions.append(
                ColumnSetRegion(
                    set_number=normalize_set_number(token),
                    header_line=header_line,
                    lines=[line],
                    set_column_span=(boundary.raw_x0, boundary.raw_x1),
                )
            )
        elif regions:
            regions[-1].lines.append(line)

    if len({r.set_number for r in regions}) < MIN_DISTINCT_SET_IDS:
        return []
    for region in regions:
        region.table_lines = body
    return regions
