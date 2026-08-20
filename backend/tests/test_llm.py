"""The LLM layer is optional; these tests pin its guard rails with a fake client.

They do not exercise a live model - no network call is made.
"""

from types import SimpleNamespace

import pytest

from hardware_sets.llm import LLMComponent, LLMHardwareSet, _merge, refine_with_llm, render_region
from hardware_sets.models import Component, HardwareSet, Location, Span
from hardware_sets.parsing.pdf import parse_pdf
from hardware_sets.pipeline import extract_hardware_sets


class FakeClient:
    def __init__(self, payload, stop_reason=None):
        self.payload = payload
        self.stop_reason = stop_reason
        self.calls = []

    @property
    def messages(self):
        return self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.payload, stop_reason=self.stop_reason)


def _set_with(component: Component, confidence: dict[str, float]) -> HardwareSet:
    component.confidence = confidence
    return HardwareSet(
        set_number="1",
        location=Location(page=1, bbox=[0, 0, 10, 10]),
        components=[component],
        confidence=0.5,
    )


def test_low_confidence_field_is_corrected_when_the_value_is_on_the_page():
    hardware_set = _set_with(Component(mfr="M", description="HINGE"), {"mfr": 0.3})
    proposal = LLMHardwareSet(set_number="1", components=[LLMComponent(mfr="MK")])
    changed = _merge(hardware_set, proposal, "3 EA HINGE TA2714 MK US26D")
    assert changed == ["component 1 mfr"]
    assert hardware_set.components[0].mfr == "MK"


def test_value_absent_from_the_source_is_rejected():
    hardware_set = _set_with(Component(mfr="M", description="HINGE"), {"mfr": 0.3})
    proposal = LLMHardwareSet(set_number="1", components=[LLMComponent(mfr="HAGER")])
    assert _merge(hardware_set, proposal, "3 EA HINGE TA2714 MK US26D") == []
    assert hardware_set.components[0].mfr == "M"


def test_confident_field_is_never_overwritten():
    hardware_set = _set_with(Component(mfr="MK", description="HINGE"), {"mfr": 0.95})
    proposal = LLMHardwareSet(set_number="1", components=[LLMComponent(mfr="SCH")])
    assert _merge(hardware_set, proposal, "3 EA HINGE TA2714 MK SCH") == []
    assert hardware_set.components[0].mfr == "MK"


def test_quantity_is_never_invented():
    hardware_set = _set_with(Component(qty=None, description="DOOR SWEEP"), {"description": 0.4})
    proposal = LLMHardwareSet(set_number="1", components=[LLMComponent(qty=1)])
    assert _merge(hardware_set, proposal, "EA DOOR SWEEP 315CN PE AL") == []
    assert hardware_set.components[0].qty is None


def test_component_count_disagreement_is_not_applied():
    hardware_set = _set_with(Component(description="HINGE"), {"description": 0.3})
    proposal = LLMHardwareSet(
        set_number="1",
        components=[LLMComponent(description="HINGE"), LLMComponent(description="LOCK")],
    )
    assert _merge(hardware_set, proposal, "HINGE LOCK") == []
    assert len(hardware_set.components) == 1


def test_refusal_leaves_the_deterministic_output_untouched(fixtures_dir):
    path = fixtures_dir / "fixture_02_list_sections.pdf"
    result = extract_hardware_sets(path)
    document = parse_pdf(path)
    before = [c.mfr for s in result.hardware_sets for c in s.components]

    client = FakeClient(payload=None, stop_reason="refusal")
    refined = refine_with_llm(result, document, client=client)

    assert [c.mfr for s in refined.hardware_sets for c in s.components] == before
    assert any("declined" in w for w in refined.warnings)


def test_region_rendering_preserves_column_spacing(fixtures_dir):
    path = fixtures_dir / "fixture_01_table_schedule.pdf"
    result = extract_hardware_sets(path)
    document = parse_pdf(path)
    text = render_region(document, result.hardware_sets[0])

    assert "[page 1]" in text
    hinge = next(line for line in text.splitlines() if "HINGE" in line and "TA2714" in line)
    assert hinge.index("TA2714") - hinge.index("HINGE") > 20


@pytest.mark.parametrize("confidence", [0.99, 1.0])
def test_confident_sets_are_not_sent_to_the_model(fixtures_dir, confidence):
    path = fixtures_dir / "fixture_01_table_schedule.pdf"
    result = extract_hardware_sets(path)
    document = parse_pdf(path)
    for hardware_set in result.hardware_sets:
        hardware_set.confidence = confidence
        for component in hardware_set.components:
            component.confidence = {k: confidence for k in component.confidence}

    client = FakeClient(payload=None)
    refine_with_llm(result, document, client=client)
    assert client.calls == []
