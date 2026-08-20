"""Run the extractor over every PDF under `samples/` and report what happened.

Built for triaging the real challenge corpus: Drive downloads keep one
subfolder per project, so this walks recursively, never stops on a bad file,
and sorts the problems to the top.

    python evals/batch_report.py
    python evals/batch_report.py --dir some/other/dir --json
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hardware_sets.pipeline import extract_hardware_sets  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Row:
    path: str
    pages: int = 0
    sets: int = 0
    components: int = 0
    not_used: int = 0
    null_qty: int = 0
    low_confidence: int = 0
    scanned_pages: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def problem(self) -> str | None:
        if self.error:
            return "ERROR"
        if self.scanned_pages:
            return "SCANNED"
        if self.sets == 0:
            return "NO SETS"
        if self.components == 0:
            return "NO COMPONENTS"
        return None


def inspect(pdf: Path, base: Path) -> Row:
    row = Row(path=str(pdf.relative_to(base)))
    try:
        result = extract_hardware_sets(pdf)
    except Exception as exc:
        row.error = f"{type(exc).__name__}: {exc}"
        return row

    row.pages = result.page_count
    row.sets = len(result.hardware_sets)
    row.components = sum(len(s.components) for s in result.hardware_sets)
    row.not_used = sum(1 for s in result.hardware_sets if s.not_used)
    row.null_qty = sum(
        1 for s in result.hardware_sets for c in s.components if c.qty is None
    )
    row.low_confidence = sum(
        1
        for s in result.hardware_sets
        if s.confidence is not None and s.confidence < 0.8
    )
    row.scanned_pages = [p.page for p in result.pages if not p.has_text]
    row.warnings = result.warnings
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=ROOT / "samples")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"No such directory: {args.dir}", file=sys.stderr)
        return 2

    pdfs = sorted(args.dir.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found under {args.dir}", file=sys.stderr)
        return 2

    rows = [inspect(pdf, args.dir) for pdf in pdfs]

    if args.json:
        print(json.dumps([asdict(r) for r in rows], indent=2))
        return 0

    width = min(max(len(r.path) for r in rows), 62)
    print(f"{'FILE':<{width}}  {'PG':>3} {'SETS':>5} {'COMP':>5} {'N/U':>4} {'NULLQ':>6}  FLAG")
    print("-" * (width + 36))
    for row in sorted(rows, key=lambda r: (r.problem is None, r.path)):
        name = row.path if len(row.path) <= width else "…" + row.path[-(width - 1):]
        print(
            f"{name:<{width}}  {row.pages:>3} {row.sets:>5} {row.components:>5} "
            f"{row.not_used:>4} {row.null_qty:>6}  {row.problem or ''}"
        )

    problems = [r for r in rows if r.problem]
    print(f"\n{len(rows)} PDFs · {sum(r.sets for r in rows)} sets · "
          f"{sum(r.components for r in rows)} components")

    if problems:
        print(f"\n{len(problems)} need attention:")
        for row in problems:
            print(f"  [{row.problem}] {row.path}")
            if row.error:
                print(f"      {row.error}")
            if row.scanned_pages:
                print(f"      no text layer on pages {row.scanned_pages}")
    else:
        print("\nno problems detected")

    flagged = [r for r in rows if not r.problem and r.low_confidence]
    if flagged:
        print(f"\n{len(flagged)} extracted but contain low-confidence sets (worth a look):")
        for row in flagged:
            print(f"  {row.path} - {row.low_confidence} set(s) below 80%")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
