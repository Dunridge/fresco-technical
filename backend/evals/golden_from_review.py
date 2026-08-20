"""Turn a human-reviewed extraction into a golden file.

This script does **not** verify anything on its own. It is the last step of a
workflow whose only source of truth is a person:

    1. Upload a real specbook in the review UI.
    2. Open every hardware set and check it against the page image beside it,
       correcting any field that is wrong.
    3. Save the corrections.
    4. Run this script to write `evals/expected/<name>.json`.

Why the guard rails matter
--------------------------
Exporting an extraction as its own expected output would score 100% by
construction - the extractor graded against its own answers. That number would
be meaningless and, worse, would look like validation.

So this script:

* refuses to export a set the reviewer never opened (`--allow-unreviewed`
  overrides, and records that it was overridden);
* counts corrections by diffing the reviewed data against what the extractor
  originally produced, server-side, rather than trusting a client-supplied
  count;
* stamps every golden with a `provenance` block so anyone reading the file can
  see how it was produced - including that nothing was changed, if that is the
  case.

    python evals/golden_from_review.py --list
    python evals/golden_from_review.py --document-id <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hardware_sets.models import ExtractionResult, HardwareSet  # noqa: E402

EVALS = Path(__file__).resolve().parent
EXPECTED = EVALS / "expected"
STORAGE = Path(
    os.environ.get("HARDWARE_SETS_STORAGE", Path(tempfile.gettempdir()) / "hardware-sets")
)
COMPONENT_FIELDS = ("qty", "description", "catalog_number", "mfr", "finish", "notes")


def _load(directory: Path) -> tuple[ExtractionResult, dict, str]:
    result = ExtractionResult.model_validate_json((directory / "result.json").read_text())
    feedback_path = directory / "feedback.json"
    feedback = json.loads(feedback_path.read_text()) if feedback_path.exists() else {}
    name_path = directory / "filename.txt"
    filename = name_path.read_text().strip() if name_path.exists() else result.source
    return result, feedback, filename


def list_documents() -> int:
    if not STORAGE.is_dir():
        print(f"No storage directory at {STORAGE}. Upload a document in the UI first.")
        return 1
    rows = []
    for directory in sorted(STORAGE.iterdir()):
        if not (directory / "result.json").exists():
            continue
        try:
            result, feedback, filename = _load(directory)
        except Exception as exc:
            print(f"  {directory.name}  (unreadable: {exc})")
            continue
        reviewed = len(feedback.get("reviewed_set_numbers", []))
        rows.append((directory.name, filename, len(result.hardware_sets), reviewed))

    if not rows:
        print(f"No documents in {STORAGE}.")
        return 1
    print(f"{'DOCUMENT ID':<34} {'SETS':>5} {'REVIEWED':>9}  FILE")
    for doc_id, filename, sets, reviewed in rows:
        print(f"{doc_id:<34} {sets:>5} {reviewed:>9}  {filename}")
    return 0


def _corrections(original: HardwareSet | None, reviewed: dict) -> int:
    """Count fields the reviewer changed, measured against the extractor's own output."""
    if original is None:
        return 0
    changed = 0
    if (original.description or None) != (reviewed.get("description") or None):
        changed += 1
    originals = {id(c): c for c in original.components}
    for index, component in enumerate(reviewed.get("components", [])):
        if index >= len(original.components):
            changed += len(COMPONENT_FIELDS)
            continue
        before = original.components[index]
        for field in COMPONENT_FIELDS:
            if (getattr(before, field) or None) != (component.get(field) or None):
                changed += 1
    del originals
    return changed


def build_golden(document_id: str, allow_unreviewed: bool, note: str | None) -> dict | None:
    directory = STORAGE / document_id
    if not directory.is_dir():
        print(f"Unknown document id {document_id}. Try --list.", file=sys.stderr)
        return None

    result, feedback, filename = _load(directory)
    reviewed_sets = feedback.get("hardware_sets")
    if not reviewed_sets:
        print(
            "This document has no saved corrections. Open it in the review UI, check "
            "each set against the page, and press Save corrections first.",
            file=sys.stderr,
        )
        return None

    reviewed_numbers = set(feedback.get("reviewed_set_numbers", []))
    unreviewed = [s["set_number"] for s in reviewed_sets if s["set_number"] not in reviewed_numbers]
    if unreviewed and not allow_unreviewed:
        print(
            f"{len(unreviewed)} of {len(reviewed_sets)} sets were never opened in the review "
            f"UI: {', '.join(unreviewed[:8])}{'…' if len(unreviewed) > 8 else ''}\n"
            "A golden must be verified by a person, not copied from the extractor's own "
            "output. Open the remaining sets, or pass --allow-unreviewed to record this "
            "golden as partially unverified.",
            file=sys.stderr,
        )
        return None

    by_number = {s.set_number: s for s in result.hardware_sets}
    corrected = sum(_corrections(by_number.get(s["set_number"]), s) for s in reviewed_sets)

    hardware_sets = []
    for entry in reviewed_sets:
        original = by_number.get(entry["set_number"])
        pages = sorted({span["page"] for span in entry.get("location", {}).get("spans", [])})
        if not pages and original is not None:
            pages = [original.location.page]
        hardware_sets.append(
            {
                "set_number": entry["set_number"],
                "description": entry.get("description"),
                "not_used": bool(entry.get("not_used")),
                "pages": pages,
                "components": [
                    {field: component.get(field) for field in COMPONENT_FIELDS}
                    for component in entry.get("components", [])
                ],
            }
        )

    return {
        "source": filename,
        "source_path": _relative_source(filename),
        "notes": note
        or "Built from a human review of a real specbook in the review UI. "
        "See evals/golden_from_review.py.",
        "provenance": {
            "verified_by": "human review in the extraction UI",
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_document": filename,
            "sets_total": len(reviewed_sets),
            "sets_reviewed": len(reviewed_numbers & {s["set_number"] for s in reviewed_sets}),
            "sets_unreviewed": len(unreviewed),
            "fields_corrected": corrected,
            "unreviewed_override": bool(unreviewed and allow_unreviewed),
            "reviewer_note": feedback.get("note"),
        },
        "hardware_sets": hardware_sets,
    }


def _relative_source(filename: str) -> str:
    """Locate the reviewed document so the evaluator can find it again."""
    name = Path(filename).name
    for root in (EVALS.parent / "samples", EVALS / "fixtures"):
        if not root.is_dir():
            continue
        for candidate in root.rglob("*.pdf"):
            if candidate.name == name:
                return str(candidate.relative_to(EVALS.parent))
    return f"samples/{name}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list reviewed documents")
    parser.add_argument("--document-id", help="document id from --list")
    parser.add_argument("--out", type=Path, help="output path (default: evals/expected/<name>.json)")
    parser.add_argument("--note", help="what this golden covers")
    parser.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="export sets that were never opened, recording the override in provenance",
    )
    args = parser.parse_args()

    if args.list or not args.document_id:
        return list_documents() if args.list else (parser.print_help() or 2)

    golden = build_golden(args.document_id, args.allow_unreviewed, args.note)
    if golden is None:
        return 1

    stem = Path(golden["source"]).stem.replace(" ", "_").lower()
    out = args.out or EXPECTED / f"real_{stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(golden, indent=2) + "\n")

    provenance = golden["provenance"]
    print(f"wrote {out}")
    print(
        f"  {provenance['sets_total']} sets, {provenance['sets_reviewed']} reviewed, "
        f"{provenance['fields_corrected']} fields corrected"
    )
    if provenance["fields_corrected"] == 0:
        print(
            "  NOTE: nothing was corrected. That is a valid outcome only if you checked "
            "each set against the page and the extraction was already right."
        )
    print("\nNow run:  python evals/evaluate.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
