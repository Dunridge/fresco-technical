"""Hardware-set header detection and region building.

Regions are cut from a single document-ordered stream of lines rather than
per page, so a set that runs past a page break simply keeps collecting lines.
Multi-page handling therefore falls out of the region model instead of needing
a separate stitching pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..parsing.layout import Document, Line

_NUMBER = r"\d{1,3}[A-Z]{0,2}(?:[.\-]\d{1,2})?"
_LETTER_ID = r"[A-Z]{1,2}"
_PREFIX = r"(?:DOOR\s+)?(?:HARDWARE|HDW|HW)"
_KIND = r"(?:SETS?|GROUPS?|HEADINGS?)"
_LABEL = r"(?:NO\.?|NUMBER|NUM|#|:)?"

SET_HEADER_RE = re.compile(
    rf"^\s*(?:(?P<prefix>{_PREFIX})[\s\-]*)?"
    rf"(?P<kind>{_KIND})\b[\s.:\-]*"
    rf"{_LABEL}\s*"
    rf"(?P<number>{_NUMBER})\b"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)

# Some schedules identify sets by letter (`SET A`, `HARDWARE GROUP B`). A bare
# letter counts only when it ends the heading or is followed by a separator -
# otherwise `SET AS FOLLOWS` would be read as set "AS".
SET_HEADER_LETTER_RE = re.compile(
    rf"^\s*(?:(?P<prefix>{_PREFIX})[\s\-]*)?"
    rf"(?P<kind>{_KIND})\b[\s.:\-]*"
    rf"{_LABEL}\s*"
    rf"(?P<number>{_LETTER_ID})"
    r"(?P<rest>\s*(?:[-\u2013\u2014:.]\s*\S.*)?)$",
    re.IGNORECASE,
)

# `HW-1` / `HDW 2` - the abbreviation carries the number with no `SET` word.
SET_HEADER_ABBREV_RE = re.compile(
    rf"^\s*(?P<prefix>HDW|HW)[\s\-#]+(?P<number>{_NUMBER})\b(?P<rest>.*)$",
    re.IGNORECASE,
)

# Longest alternative first, anchored with \b, so `CONTINUED` is not consumed
# as `CONT` leaving `INUED` behind as the set description.
CONTINUATION_RE = re.compile(
    r"\(?\s*(?:CONT(?:INUED|'?D)?|CON'?T)\b\.?\s*\)?", re.IGNORECASE
)

# `SET`/`GROUP` alone is too common in prose; require a header-ish line.
MAX_HEADER_LINE_LENGTH = 90

COLUMN_HEADER_TOKENS = {
    "QTY", "QTY.", "QUANTITY", "UNIT", "U/M", "UOM", "DESCRIPTION", "ITEM",
    "CATALOG", "PRODUCT", "MODEL", "MFR", "MFR.", "MFG", "MFG.", "MANUFACTURER",
    "FINISH", "FIN", "FIN.", "NOTES", "REMARKS", "NUMBER", "NO", "NO.",
}


@dataclass
class SetHeader:
    line: Line
    set_number: str
    inline_description: str | None
    is_continuation: bool
    stream_index: int


@dataclass
class SetRegion:
    header: SetHeader
    lines: list[Line] = field(default_factory=list)

    @property
    def set_number(self) -> str:
        return self.header.set_number

    @property
    def pages(self) -> list[int]:
        seen: list[int] = []
        for line in [self.header.line, *self.lines]:
            if line.page not in seen:
                seen.append(line.page)
        return seen


def normalize_set_number(raw: str) -> str:
    value = raw.strip().upper().lstrip("0") or "0"
    return value


def match_set_header(line: Line) -> tuple[str, str | None, bool] | None:
    text = line.text.strip()
    if not text or len(text) > MAX_HEADER_LINE_LENGTH:
        return None

    for pattern in (SET_HEADER_RE, SET_HEADER_LETTER_RE, SET_HEADER_ABBREV_RE):
        match = pattern.match(text)
        if match is None:
            continue
        groups = match.groupdict()
        kind = (groups.get("kind") or "").upper()
        prefix = (groups.get("prefix") or "").upper()
        # A bare "GROUP 3" is too common in prose to trust on its own;
        # `HARDWARE`/`HW`/`HDW` make it unambiguous.
        if not prefix and kind.startswith("GROUP"):
            continue

        rest = groups.get("rest") or ""
        is_continuation = bool(CONTINUATION_RE.search(rest))
        description = CONTINUATION_RE.sub("", rest)
        description = description.strip().lstrip("-\u2013\u2014:.,)( ").strip()
        return normalize_set_number(groups["number"]), description or None, is_continuation
    return None


def is_column_header_line(line: Line) -> bool:
    tokens = [w.text.strip().upper() for w in line.words if w.text.strip()]
    if len(tokens) < 2:
        return False
    hits = sum(1 for token in tokens if token in COLUMN_HEADER_TOKENS)
    return hits >= 2 and hits / len(tokens) >= 0.5


def build_line_stream(document: Document, skip: set[tuple[int, int]] | None = None) -> list[Line]:
    skip = skip or set()
    stream: list[Line] = []
    for page in sorted(document.pages, key=lambda p: p.number):
        for line in page.content_lines:
            if (page.number, line.index) in skip:
                continue
            stream.append(line)
    return stream


def find_set_regions(stream: list[Line]) -> list[SetRegion]:
    """Split the line stream into one region per hardware set."""
    headers: list[SetHeader] = []
    for position, line in enumerate(stream):
        matched = match_set_header(line)
        if matched is None:
            continue
        number, description, is_continuation = matched
        headers.append(
            SetHeader(
                line=line,
                set_number=number,
                inline_description=description,
                is_continuation=is_continuation,
                stream_index=position,
            )
        )

    regions: list[SetRegion] = []
    for order, header in enumerate(headers):
        end = headers[order + 1].stream_index if order + 1 < len(headers) else len(stream)
        body = stream[header.stream_index + 1 : end]

        # An explicit `(CONT'D)` header, or a repeat of the number we are
        # already inside, continues the active set instead of opening a new one.
        if regions and (header.is_continuation or header.set_number == regions[-1].set_number):
            regions[-1].lines.extend(body)
            continue
        regions.append(SetRegion(header=header, lines=body))
    return regions


LEGEND_PAIR_RE = re.compile(
    r"\b([A-Z0-9]{1,6})\s*[=]\s*"
    r"((?:[A-Z][A-Z0-9&.'\-]*)(?:\s+(?![A-Z0-9]{1,6}\s*=)[A-Z][A-Z0-9&.'\-]*)*)"
)


def extract_legend(stream: list[Line]) -> dict[str, str]:
    """Collect `CODE = MEANING` abbreviation tables printed on the page.

    Specbooks routinely print their own manufacturer key; when present it is the
    strongest possible evidence for an otherwise ambiguous code.
    """
    legend: dict[str, str] = {}
    for line in stream:
        for code, meaning in LEGEND_PAIR_RE.findall(line.text.upper()):
            cleaned = meaning.strip(" .,-")
            if cleaned and code not in legend:
                legend[code] = cleaned
    return legend
