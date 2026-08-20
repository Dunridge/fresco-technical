"""Evaluation harness for the hardware-set extractor.

Compares extractor output against the manually verified golden corpus and
reports per-field metrics plus the failure categories listed in PLAN.md.

Headline metric - `overall accuracy` - is the share of individual assertions
that are correct:

    per expected set        : set_number, description, start page      (3)
    per expected component  : qty, description, catalog_number,
                              mfr, finish, notes                       (6)

An expected set or component that was never matched scores zero for all of its
assertions. A predicted set or component with no expected counterpart adds the
same number of failed assertions, so hallucinated output is penalised exactly
as heavily as missed output.

Run:  python evals/evaluate.py [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hardware_sets.pipeline import extract_hardware_sets  # noqa: E402

EVALS = Path(__file__).parent
ROOT = EVALS.parent
FIXTURES = EVALS / "fixtures"
EXPECTED = EVALS / "expected"

COMPONENT_FIELDS = ("qty", "description", "catalog_number", "mfr", "finish", "notes")
SET_ASSERTIONS = 3


def normalize(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip().upper().strip(" .,;:-")
    return text or None


def similarity(a: str | None, b: str | None) -> float:
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    if a == b:
        return 1.0
    a_tokens, b_tokens = set(a.split()), set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


@dataclass
class Counter:
    correct: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.total += 1
        self.correct += int(ok)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 1.0


@dataclass
class Report:
    fixture: str
    sets_expected: int = 0
    sets_predicted: int = 0
    sets_matched: int = 0
    components_expected: int = 0
    components_predicted: int = 0
    components_matched: int = 0
    fields: dict[str, Counter] = field(default_factory=dict)
    set_number: Counter = field(default_factory=Counter)
    set_description: Counter = field(default_factory=Counter)
    location: Counter = field(default_factory=Counter)
    multi_page: Counter = field(default_factory=Counter)
    not_used: Counter = field(default_factory=Counter)
    checks_correct: int = 0
    checks_total: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)

    def counter(self, name: str) -> Counter:
        return self.fields.setdefault(name, Counter())

    def fail(self, category: str, detail: str) -> None:
        self.failures.append((category, detail))

    @property
    def set_recall(self) -> float:
        return self.sets_matched / self.sets_expected if self.sets_expected else 1.0

    @property
    def set_precision(self) -> float:
        return self.sets_matched / self.sets_predicted if self.sets_predicted else 1.0

    @property
    def component_recall(self) -> float:
        return (
            self.components_matched / self.components_expected
            if self.components_expected
            else 1.0
        )

    @property
    def component_precision(self) -> float:
        return (
            self.components_matched / self.components_predicted
            if self.components_predicted
            else 1.0
        )

    @property
    def overall(self) -> float:
        return self.checks_correct / self.checks_total if self.checks_total else 1.0


def align_components(expected: list[dict], predicted: list) -> list[tuple[int | None, int | None]]:
    """One-to-one alignment, best description similarity first."""
    scored: list[tuple[float, int, int]] = []
    for i, exp in enumerate(expected):
        for j, pred in enumerate(predicted):
            score = similarity(normalize(exp.get("description")), normalize(pred.description))
            score += 0.25 * similarity(
                normalize(exp.get("catalog_number")), normalize(pred.catalog_number)
            )
            scored.append((score, i, j))
    scored.sort(key=lambda item: -item[0])

    used_expected: set[int] = set()
    used_predicted: set[int] = set()
    pairs: list[tuple[int | None, int | None]] = []
    for score, i, j in scored:
        if score <= 0 or i in used_expected or j in used_predicted:
            continue
        pairs.append((i, j))
        used_expected.add(i)
        used_predicted.add(j)
    pairs += [(i, None) for i in range(len(expected)) if i not in used_expected]
    pairs += [(None, j) for j in range(len(predicted)) if j not in used_predicted]
    return pairs


def evaluate_fixture(pdf: Path, golden: dict) -> Report:
    report = Report(fixture=pdf.name)
    result = extract_hardware_sets(pdf)
    predicted = {s.set_number: s for s in result.hardware_sets}
    expected_sets = golden["hardware_sets"]

    report.sets_expected = len(expected_sets)
    report.sets_predicted = len(result.hardware_sets)

    for expected in expected_sets:
        number = expected["set_number"]
        report.checks_total += SET_ASSERTIONS
        match = predicted.pop(number, None)
        if match is None:
            report.fail("SET_DETECTION", f"set {number} not found")
            report.set_number.add(False)
            report.set_description.add(False)
            report.location.add(False)
            report.checks_total += len(expected["components"]) * len(COMPONENT_FIELDS)
            report.components_expected += len(expected["components"])
            continue

        report.sets_matched += 1
        report.set_number.add(True)
        report.checks_correct += 1

        description_ok = normalize(match.description) == normalize(expected["description"])
        report.set_description.add(description_ok)
        report.checks_correct += int(description_ok)
        if not description_ok:
            report.fail(
                "SET_DETECTION",
                f"set {number} description {match.description!r} != {expected['description']!r}",
            )

        expected_pages = expected["pages"]
        page_ok = match.location.page == expected_pages[0]
        report.location.add(page_ok)
        report.checks_correct += int(page_ok)
        if not page_ok:
            report.fail(
                "LOCATION", f"set {number} starts on page {match.location.page}, expected {expected_pages[0]}"
            )

        span_pages = [s.page for s in match.location.spans] or [match.location.page]
        spans_ok = span_pages == expected_pages
        if len(expected_pages) > 1 or len(span_pages) > 1:
            report.multi_page.add(spans_ok)
            if not spans_ok:
                report.fail(
                    "MULTI_PAGE", f"set {number} covers pages {span_pages}, expected {expected_pages}"
                )

        report.not_used.add(match.not_used == expected["not_used"])
        if match.not_used != expected["not_used"]:
            report.fail("NOT_USED", f"set {number} not_used={match.not_used}")

        _evaluate_components(report, number, expected["components"], match.components)

    for number, spurious in predicted.items():
        report.fail("SET_DETECTION", f"set {number} was extracted but is not in the golden output")
        report.checks_total += SET_ASSERTIONS + len(spurious.components) * len(COMPONENT_FIELDS)
        report.components_predicted += len(spurious.components)

    return report


def _evaluate_components(report: Report, set_number: str, expected: list[dict], predicted: list) -> None:
    report.components_expected += len(expected)
    report.components_predicted += len(predicted)

    for i, j in align_components(expected, predicted):
        if i is None:
            report.fail("COMPONENT_DETECTION", f"set {set_number}: extra component {predicted[j].description!r}")
            report.checks_total += len(COMPONENT_FIELDS)
            continue
        if j is None:
            report.fail("COMPONENT_DETECTION", f"set {set_number}: missed component {expected[i].get('description')!r}")
            report.checks_total += len(COMPONENT_FIELDS)
            for name in COMPONENT_FIELDS:
                report.counter(name).add(False)
            continue

        report.components_matched += 1
        exp, pred = expected[i], predicted[j]
        for name in COMPONENT_FIELDS:
            expected_value = exp.get(name)
            actual_value = getattr(pred, name)
            if name == "qty":
                ok = expected_value == actual_value
            else:
                ok = normalize(expected_value) == normalize(actual_value)
            report.counter(name).add(ok)
            report.checks_total += 1
            report.checks_correct += int(ok)
            if not ok:
                category = "MFR_FINISH" if name in ("mfr", "finish") else "FIELD_MAPPING"
                report.fail(
                    category,
                    f"set {set_number} {exp.get('description')!r}.{name}: "
                    f"got {actual_value!r}, expected {expected_value!r}",
                )


def print_report(report: Report) -> None:
    print(f"\n=== {report.fixture} ===")
    print(
        f"  sets       expected={report.sets_expected} predicted={report.sets_predicted} "
        f"matched={report.sets_matched} recall={report.set_recall:.1%} precision={report.set_precision:.1%}"
    )
    print(
        f"  components expected={report.components_expected} predicted={report.components_predicted} "
        f"matched={report.components_matched} recall={report.component_recall:.1%} "
        f"precision={report.component_precision:.1%}"
    )
    for name in COMPONENT_FIELDS:
        counter = report.counter(name)
        print(f"    {name:<16} {counter.accuracy:>6.1%}  ({counter.correct}/{counter.total})")
    print(f"    {'set_number':<16} {report.set_number.accuracy:>6.1%}")
    print(f"    {'set_description':<16} {report.set_description.accuracy:>6.1%}")
    print(f"    {'location(page)':<16} {report.location.accuracy:>6.1%}")
    if report.multi_page.total:
        print(f"    {'multi_page':<16} {report.multi_page.accuracy:>6.1%}  ({report.multi_page.correct}/{report.multi_page.total})")
    print(f"    {'not_used':<16} {report.not_used.accuracy:>6.1%}")
    print(f"  OVERALL {report.overall:.1%}  ({report.checks_correct}/{report.checks_total} assertions)")
    if report.failures:
        print("  failures:")
        for category, detail in report.failures:
            print(f"    [{category}] {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the hardware-set evaluation corpus.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable metrics")
    args = parser.parse_args()

    reports: list[Report] = []
    skipped: list[str] = []
    for golden_path in sorted(EXPECTED.glob("*.json")):
        golden = json.loads(golden_path.read_text())
        # `source_path` lets a golden reference a real specbook under samples/,
        # which is not committed. Those are skipped rather than failing the run.
        pdf = (
            (ROOT / golden["source_path"]).resolve()
            if golden.get("source_path")
            else FIXTURES / golden["source"]
        )
        if not pdf.exists():
            if golden.get("source_path"):
                skipped.append(f"{golden_path.name} (source not present: {golden['source_path']})")
                continue
            print(
                f"missing fixture {pdf}; run `python evals/generate_fixtures.py` first",
                file=sys.stderr,
            )
            return 2
        reports.append(evaluate_fixture(pdf, golden))

    if not reports:
        print("no goldens could be evaluated", file=sys.stderr)
        return 2

    total_correct = sum(r.checks_correct for r in reports)
    total_checks = sum(r.checks_total for r in reports)
    overall = total_correct / total_checks if total_checks else 1.0

    if args.json:
        print(
            json.dumps(
                {
                    "overall_accuracy": overall,
                    "fixtures": [
                        {
                            "fixture": r.fixture,
                            "overall": r.overall,
                            "set_recall": r.set_recall,
                            "component_recall": r.component_recall,
                            "fields": {n: r.counter(n).accuracy for n in COMPONENT_FIELDS},
                            "failures": [{"category": c, "detail": d} for c, d in r.failures],
                        }
                        for r in reports
                    ],
                },
                indent=2,
            )
        )
        return 0

    for report in reports:
        print_report(report)

    for entry in skipped:
        print(f"\nskipped {entry}")

    print("\n" + "=" * 60)
    print(f"CORPUS OVERALL ACCURACY: {overall:.1%}  ({total_correct}/{total_checks} assertions)")
    categories: dict[str, int] = {}
    for report in reports:
        for category, _ in report.failures:
            categories[category] = categories.get(category, 0) + 1
    if categories:
        print("failures by category: " + ", ".join(f"{k}={v}" for k, v in sorted(categories.items())))
    else:
        print("no failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
