"""End-to-end behaviour, one test per caveat the challenge calls out."""

import pytest

from hardware_sets.models import ExtractionResult
from hardware_sets.pipeline import extract_hardware_sets


@pytest.fixture(scope="module")
def results(request):
    fixtures = request.getfixturevalue("fixtures_dir")
    return {path.stem: extract_hardware_sets(path) for path in sorted(fixtures.glob("*.pdf"))}


def test_every_fixture_yields_a_valid_result(results):
    for name, result in results.items():
        assert isinstance(result, ExtractionResult), name
        ExtractionResult.model_validate(result.model_dump())


@pytest.mark.parametrize(
    "fixture,numbers",
    [
        ("fixture_01_table_schedule", ["1", "2", "3", "4", "5"]),
        ("fixture_02_list_sections", ["1", "2A", "3", "4"]),
        ("fixture_03_alt_schema", ["3A", "4", "5"]),
        ("fixture_04_merged_columns", ["7", "8", "9", "12"]),
    ],
)
def test_all_sets_are_found(results, fixture, numbers):
    assert [s.set_number for s in results[fixture].hardware_sets] == numbers


def test_not_used_sets_are_extracted_with_no_components(results):
    not_used = [
        s
        for result in results.values()
        for s in result.hardware_sets
        if s.not_used
    ]
    assert len(not_used) == 4
    assert all(s.components == [] for s in not_used)
    assert all(s.description for s in not_used)


def test_missing_quantity_is_null_not_guessed(results):
    sweep = _find(results["fixture_01_table_schedule"], "2", "DOOR SWEEP")
    assert sweep.qty is None
    assert sweep.catalog_number == "315CN"

    silencer = _find(results["fixture_03_alt_schema"], "3A", "SILENCER")
    assert silencer.qty is None


def test_ambiguous_pe_resolves_by_column_context_not_by_value(results):
    # Same code, opposite meaning, decided by the company its column keeps.
    as_manufacturer = _find(results["fixture_01_table_schedule"], "2", "THRESHOLD")
    assert as_manufacturer.mfr == "PE"
    assert as_manufacturer.finish == "AL"

    as_finish = _find(results["fixture_02_list_sections"], "2A", "FLOOR STOP")
    assert as_finish.finish == "PE"
    assert as_finish.mfr == "ROC"


def test_ambiguous_no_resolves_to_a_manufacturer(results):
    closer = _find(results["fixture_02_list_sections"], "1", "SURFACE CLOSER")
    assert closer.mfr == "NO"
    assert closer.finish == "689"


def test_merged_manufacturer_finish_cell_is_split(results):
    hinge = _find(results["fixture_04_merged_columns"], "8", "HINGE")
    assert (hinge.mfr, hinge.finish) == ("PE", "US26D")


def test_multi_page_set_keeps_its_components_together(results):
    spanning = _set(results["fixture_01_table_schedule"], "4")
    assert [s.page for s in spanning.location.spans] == [2, 3]
    assert len(spanning.components) == 6
    assert spanning.components[-1].description == "KICK PLATE"


def test_explicit_continuation_header_merges_into_the_same_set(results):
    result = results["fixture_03_alt_schema"]
    assert [s.set_number for s in result.hardware_sets].count("4") == 1
    spanning = _set(result, "4")
    assert [s.page for s in spanning.location.spans] == [1, 2]
    assert len(spanning.components) == 4


def test_wrapped_description_is_joined_to_its_component(results):
    lock = _find(results["fixture_01_table_schedule"], "4", "ELECTRIFIED MORTISE")
    assert lock.description == "ELECTRIFIED MORTISE LOCK, FAIL SECURE"


def test_boilerplate_between_sets_is_not_absorbed(results):
    seals = _find(results["fixture_04_merged_columns"], "7", "SEALS")
    assert seals.description == "SEALS"
    assert "ANSI" not in (seals.notes or "")


def test_running_headers_and_footers_do_not_become_components(results):
    for result in results.values():
        for hardware_set in result.hardware_sets:
            for component in hardware_set.components:
                assert "08 71 00" not in (component.description or "")
                assert "ELEMENTARY" not in (component.description or "")


def test_locations_are_meaningful(results):
    for name, result in results.items():
        pages = {p.page: p for p in result.pages}
        for hardware_set in result.hardware_sets:
            assert hardware_set.location.page in pages, name
            assert hardware_set.location.bbox is not None
            for span in hardware_set.location.spans:
                x0, y0, x1, y1 = span.bbox
                page = pages[span.page]
                assert 0 <= x0 < x1 <= page.width
                assert 0 <= y0 < y1 <= page.height
            for component in hardware_set.components:
                assert component.location is not None
                assert component.location.page in pages


def test_confidence_scores_are_reported(results):
    for result in results.values():
        for hardware_set in result.hardware_sets:
            assert hardware_set.confidence is not None
            assert 0.0 <= hardware_set.confidence <= 1.0
            for component in hardware_set.components:
                assert component.confidence
                assert all(0.0 <= v <= 1.0 for v in component.confidence.values())


def test_page_legend_is_reported(results):
    legend = results["fixture_03_alt_schema"].legend
    assert legend["PE"] == "PEMKO"
    assert legend["NO"] == "NORTON"


def test_pdfplumber_backend_agrees_with_pymupdf(fixtures_dir):
    path = fixtures_dir / "fixture_01_table_schedule.pdf"
    a = extract_hardware_sets(path, backend="pymupdf")
    b = extract_hardware_sets(path, backend="pdfplumber")
    assert _shape(a) == _shape(b)


def _shape(result):
    return [
        (s.set_number, [(c.qty, c.description, c.mfr, c.finish) for c in s.components])
        for s in result.hardware_sets
    ]


def _set(result, number):
    return next(s for s in result.hardware_sets if s.set_number == number)


def _find(result, number, description):
    hardware_set = _set(result, number)
    return next(c for c in hardware_set.components if (c.description or "").startswith(description))
