"""End-to-end extraction pipeline.

    PDF -> layout -> frame removal -> set regions -> columns -> components
        -> normalization -> HardwareSet[]

The pass over set regions runs twice. The first pass learns which component
field each column *position* carries across the whole document; the second pass
feeds that back so a set whose manufacturer column happens to contain nothing
but ambiguous codes is still resolved from document-level structure.
"""

from __future__ import annotations

from pathlib import Path

from .classification.columns import Column
from .detection.column_sets import ColumnSetRegion, find_column_set_regions
from .detection.sets import SetRegion, build_line_stream, extract_legend, find_set_regions
from .extraction.components import RegionExtraction, extract_region
from .models import ExtractionResult, Field_, HardwareSet, Location, PageInfo, Span
from .normalization.normalize import normalize_result
from .parsing.frames import detect_frame_lines
from .parsing.layout import Document, Line, bbox_union
from .parsing.pdf import parse_pdf

CONFIDENT_COLUMN_SCORE = 0.6


def extract_hardware_sets(
    path: str | Path,
    backend: str = "pymupdf",
    use_llm: bool = False,
) -> ExtractionResult:
    document = parse_pdf(path, backend=backend)
    result = _extract_from_document(document)
    if use_llm:
        from .llm import refine_with_llm

        result = refine_with_llm(result, document)
    return normalize_result(result)


def _extract_from_document(document: Document) -> ExtractionResult:
    warnings: list[str] = []
    pages = [
        PageInfo(page=p.number, width=p.width, height=p.height, has_text=p.has_text)
        for p in document.pages
    ]
    scanned = [p.page for p in pages if not p.has_text]
    if scanned:
        warnings.append(
            f"Pages {scanned} contain little or no extractable text; they may be scanned images. "
            "Run them through OCR before extraction."
        )

    frames = detect_frame_lines(document)
    stream = build_line_stream(document, skip=frames)
    legend = extract_legend(stream)
    regions: list[SetRegion | ColumnSetRegion] = list(find_set_regions(stream))

    if not regions:
        # A second layout family prints one continuous table whose leftmost
        # column carries the set identifier, with no header lines at all.
        regions = list(find_column_set_regions(stream))
        if regions:
            warnings.append(
                f"No set headers found; read {len(regions)} sets from a table with a "
                "SET column instead."
            )

    if not regions:
        warnings.append("No hardware-set headers were found in this document.")

    first_pass = [extract_region(**_region_args(r), legend=legend) for r in regions]
    hints = _document_column_hints(first_pass)
    extractions = [
        extract_region(**_region_args(r), legend=legend, document_hints=hints)
        for r in regions
    ]

    hardware_sets = [
        _build_hardware_set(region, extraction)
        for region, extraction in zip(regions, extractions)
    ]

    return ExtractionResult(
        source=document.source,
        page_count=len(document.pages),
        pages=pages,
        hardware_sets=hardware_sets,
        legend=legend,
        warnings=warnings,
    )


def _region_args(region: SetRegion | ColumnSetRegion) -> dict:
    """A set-column region's rows carry no header of their own.

    The table's single header row sits above every set in the table, and the set
    identifier itself is not a component field, so both are passed explicitly
    rather than inferred from the rows.
    """
    if isinstance(region, ColumnSetRegion):
        return {
            "lines": region.lines,
            "header_line": region.header_line,
            "geometry_lines": region.table_lines,
        }
    return {"lines": region.lines}


def _document_column_hints(extractions: list[RegionExtraction]) -> dict[int, Field_]:
    """Learn `column x position -> field` from the sets that classified cleanly."""
    votes: dict[int, dict[Field_, float]] = {}
    for extraction in extractions:
        for column in extraction.columns:
            if column.field_ is Field_.UNKNOWN or column.score < CONFIDENT_COLUMN_SCORE:
                continue
            key = round(column.raw_x0)
            votes.setdefault(key, {}).setdefault(column.field_, 0.0)
            votes[key][column.field_] += column.score
    return {key: max(fields, key=fields.get) for key, fields in votes.items() if fields}


def _build_hardware_set(
    region: SetRegion | ColumnSetRegion, extraction: RegionExtraction
) -> HardwareSet:
    if isinstance(region, ColumnSetRegion):
        return _build_column_hardware_set(region, extraction)

    description = region.header.inline_description
    if description is None and extraction.description_lines:
        description = " ".join(line.text.strip() for line in extraction.description_lines).strip()

    covered = [region.header.line, *extraction.description_lines]
    covered += [
        line
        for component in extraction.components
        if component.location is not None
        for line in _lines_of(region, component.location)
    ]
    if extraction.header_line is not None:
        covered.append(extraction.header_line)

    spans = _spans_for_lines(covered)
    primary = spans[0] if spans else Span(page=region.header.line.page, bbox=region.header.line.bbox)

    return HardwareSet(
        set_number=region.set_number,
        description=description or None,
        location=Location(
            page=primary.page,
            bbox=primary.bbox,
            line_range=primary.line_range,
            spans=spans,
        ),
        components=extraction.components,
        not_used=extraction.not_used,
        confidence=_set_confidence(extraction),
        column_mapping=_column_mapping(extraction.columns),
    )


def _build_column_hardware_set(
    region: ColumnSetRegion, extraction: RegionExtraction
) -> HardwareSet:
    """A set-column set owns exactly its own rows; the table header is shared."""
    _strip_set_id_from_description(region, extraction)
    spans = _spans_for_lines(region.lines)
    primary = spans[0] if spans else Span(page=region.header_line.page, bbox=region.header_line.bbox)
    return HardwareSet(
        set_number=region.set_number,
        description=None,
        location=Location(
            page=primary.page,
            bbox=primary.bbox,
            line_range=primary.line_range,
            spans=spans,
        ),
        components=extraction.components,
        not_used=extraction.not_used,
        confidence=_set_confidence(extraction),
        column_mapping=_column_mapping(extraction.columns),
    )


def _strip_set_id_from_description(
    region: ColumnSetRegion, extraction: RegionExtraction
) -> None:
    """Remove the set identifier from the row that carries it.

    In these schedules the set column often shares its x-range with the
    component description, so the identifier lands at the front of the first
    component's description rather than in a column of its own.
    """
    if not extraction.components:
        return
    first = extraction.components[0]
    if not first.description:
        return
    head, _, rest = first.description.partition(" ")
    if head.rstrip(".:").upper() == region.set_number.upper() and rest.strip():
        first.description = rest.strip()


def _lines_of(region: SetRegion, span: Span) -> list[Line]:
    if span.line_range is None:
        return []
    low, high = span.line_range
    return [
        line
        for line in region.lines
        if line.page == span.page and low <= line.index <= high
    ]


def _spans_for_lines(lines: list[Line]) -> list[Span]:
    by_page: dict[int, list[Line]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)
    spans: list[Span] = []
    for page in sorted(by_page):
        page_lines = by_page[page]
        spans.append(
            Span(
                page=page,
                bbox=[round(v, 2) for v in bbox_union([ln.bbox for ln in page_lines])],
                line_range=[
                    min(ln.index for ln in page_lines),
                    max(ln.index for ln in page_lines),
                ],
            )
        )
    return spans


def _set_confidence(extraction: RegionExtraction) -> float | None:
    scores = [
        value
        for component in extraction.components
        for value in component.confidence.values()
    ]
    if not scores:
        return 1.0 if extraction.not_used else None
    base = sum(scores) / len(scores)
    if extraction.header_line is not None:
        base = min(base + 0.05, 1.0)
    return round(base, 3)


def _column_mapping(columns: list[Column]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in columns:
        if column.field_ is Field_.UNKNOWN:
            continue
        mapping[f"x{round(column.raw_x0)}"] = column.field_.value
    return mapping
