"""Final validation and normalization.

Everything here is conservative: values are cleaned and obviously empty strings
become `null`, but no missing value is ever filled in.
"""

from __future__ import annotations

import re

from ..classification import vocab
from ..models import Component, ExtractionResult, HardwareSet

EMPTY_TOKENS = {"", "-", "--", "---", "N/A", "NA", "NONE", ".", "N.A."}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = re.sub(r"\s+", " ", value).strip().strip(" .,;:-")
    if collapsed.upper() in EMPTY_TOKENS:
        return None
    return collapsed or None


def normalize_component(component: Component) -> Component:
    component.description = _clean_text(component.description)
    component.catalog_number = _clean_text(component.catalog_number)
    component.mfr = _clean_text(component.mfr)
    component.finish = _clean_text(component.finish)
    component.notes = _clean_text(component.notes)
    if component.mfr:
        component.mfr = component.mfr.upper()
    if component.finish:
        component.finish = component.finish.upper()
    if component.qty is not None and component.qty <= 0:
        component.qty = None
    return component


def normalize_hardware_set(hardware_set: HardwareSet) -> HardwareSet:
    hardware_set.description = _clean_text(hardware_set.description)
    hardware_set.components = [normalize_component(c) for c in hardware_set.components]
    if not hardware_set.components and hardware_set.description:
        hardware_set.not_used = hardware_set.not_used or vocab.contains_not_used_marker(
            hardware_set.description
        )
    if hardware_set.not_used and hardware_set.confidence is None:
        hardware_set.confidence = 1.0
    return hardware_set


def normalize_result(result: ExtractionResult) -> ExtractionResult:
    result.hardware_sets = [normalize_hardware_set(s) for s in result.hardware_sets]
    _warn_on_duplicate_sets(result)
    return result


def _warn_on_duplicate_sets(result: ExtractionResult) -> None:
    seen: dict[str, int] = {}
    for hardware_set in result.hardware_sets:
        seen[hardware_set.set_number] = seen.get(hardware_set.set_number, 0) + 1
    duplicates = sorted(number for number, count in seen.items() if count > 1)
    if duplicates:
        result.warnings.append(
            f"Set numbers appear more than once and were kept separate: {duplicates}"
        )
