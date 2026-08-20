"""The golden exporter must not let an unverified extraction become ground truth."""

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))


@pytest.fixture
def workspace(tmp_path, monkeypatch, fixtures_dir):
    """A storage directory shaped like the one the API writes."""
    monkeypatch.setenv("HARDWARE_SETS_STORAGE", str(tmp_path))
    import golden_from_review

    importlib.reload(golden_from_review)

    sys.path.insert(0, str(ROOT / "src"))
    from hardware_sets.pipeline import extract_hardware_sets

    result = extract_hardware_sets(fixtures_dir / "fixture_01_table_schedule.pdf")
    directory = tmp_path / ("a" * 32)
    directory.mkdir(parents=True)
    (directory / "result.json").write_text(json.dumps(result.model_dump(mode="json")))
    (directory / "filename.txt").write_text("fixture_01_table_schedule.pdf")
    return golden_from_review, directory, result


def _write_feedback(directory, result, reviewed, mutate=None):
    payload = json.loads(json.dumps(result.model_dump(mode="json")))["hardware_sets"]
    if mutate:
        mutate(payload)
    (directory / "feedback.json").write_text(
        json.dumps({"hardware_sets": payload, "reviewed_set_numbers": reviewed, "note": None})
    )


def test_refuses_when_no_corrections_were_saved(workspace):
    module, directory, _ = workspace
    assert module.build_golden(directory.name, allow_unreviewed=False, note=None) is None


def test_refuses_sets_the_reviewer_never_opened(workspace):
    """The whole point: an unreviewed export would grade the extractor on its own output."""
    module, directory, result = workspace
    _write_feedback(directory, result, reviewed=["1"])
    assert module.build_golden(directory.name, allow_unreviewed=False, note=None) is None


def test_exports_when_every_set_was_reviewed(workspace):
    module, directory, result = workspace
    every = [s.set_number for s in result.hardware_sets]
    _write_feedback(directory, result, reviewed=every)

    golden = module.build_golden(directory.name, allow_unreviewed=False, note=None)
    assert golden is not None
    assert [s["set_number"] for s in golden["hardware_sets"]] == every
    assert golden["provenance"]["sets_unreviewed"] == 0
    assert golden["provenance"]["verified_by"] == "human review in the extraction UI"


def test_corrections_are_counted_against_the_extractor_output(workspace):
    module, directory, result = workspace
    every = [s.set_number for s in result.hardware_sets]

    def mutate(payload):
        payload[0]["components"][0]["mfr"] = "MCKINNEY"
        payload[0]["components"][1]["finish"] = "US26D"

    _write_feedback(directory, result, reviewed=every, mutate=mutate)
    golden = module.build_golden(directory.name, allow_unreviewed=False, note=None)
    assert golden["provenance"]["fields_corrected"] == 2


def test_zero_corrections_is_recorded_not_hidden(workspace):
    """A rubber stamp must be visible in the file, not silently indistinguishable."""
    module, directory, result = workspace
    every = [s.set_number for s in result.hardware_sets]
    _write_feedback(directory, result, reviewed=every)
    golden = module.build_golden(directory.name, allow_unreviewed=False, note=None)
    assert golden["provenance"]["fields_corrected"] == 0


def test_override_is_recorded_in_provenance(workspace):
    module, directory, result = workspace
    _write_feedback(directory, result, reviewed=["1"])
    golden = module.build_golden(directory.name, allow_unreviewed=True, note=None)
    assert golden is not None
    assert golden["provenance"]["unreviewed_override"] is True
    assert golden["provenance"]["sets_unreviewed"] == len(result.hardware_sets) - 1


def test_unknown_document_id_is_rejected(workspace):
    module, _, _ = workspace
    assert module.build_golden("does-not-exist", allow_unreviewed=False, note=None) is None
