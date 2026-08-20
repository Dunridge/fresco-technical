"""Public extraction schema.

The field names in `Component` and `HardwareSet` are fixed by the challenge
specification. Everything added beyond that (spans, confidence, evidence) is
additive and optional so the core contract stays stable.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Field_(str, Enum):
    """Component fields that a detected column can be mapped onto."""

    QTY = "qty"
    UNIT = "unit"
    DESCRIPTION = "description"
    CATALOG_NUMBER = "catalog_number"
    MFR = "mfr"
    FINISH = "finish"
    NOTES = "notes"
    UNKNOWN = "unknown"


class Span(BaseModel):
    """One contiguous region of a set on a single page.

    A set that continues across a page break has one span per page.
    """

    page: int
    bbox: list[float]
    line_range: list[int] | None = None


class Location(BaseModel):
    """Where a hardware set lives in the source document.

    `page`/`bbox` always describe where the set *starts*, which keeps the shape
    the challenge asks for. `spans` carries the full footprint for sets that
    cross a page break.
    """

    page: int
    bbox: list[float] | None = None
    line_range: list[int] | None = None
    spans: list[Span] = Field(default_factory=list)


class Component(BaseModel):
    qty: int | None = None
    description: str | None = None
    catalog_number: str | None = None
    mfr: str | None = None
    finish: str | None = None
    notes: str | None = None

    location: Span | None = None
    confidence: dict[str, float] = Field(default_factory=dict)


class HardwareSet(BaseModel):
    set_number: str
    description: str | None = None
    location: Location
    components: list[Component] = Field(default_factory=list)

    not_used: bool = False
    confidence: float | None = None
    column_mapping: dict[str, str] = Field(default_factory=dict)


class PageInfo(BaseModel):
    page: int
    width: float
    height: float
    has_text: bool


class ExtractionResult(BaseModel):
    source: str
    page_count: int
    pages: list[PageInfo] = Field(default_factory=list)
    hardware_sets: list[HardwareSet] = Field(default_factory=list)
    legend: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
