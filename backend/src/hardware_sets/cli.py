"""Command line interface.

    python -m hardware_sets <pdf> [--out result.json] [--llm]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import extract_hardware_sets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hardware-sets",
        description="Extract hardware sets from a Division 08 specification PDF.",
    )
    parser.add_argument("pdf", type=Path, help="path to the specification PDF")
    parser.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    parser.add_argument(
        "--backend",
        choices=("pymupdf", "pdfplumber"),
        default="pymupdf",
        help="PDF parsing backend (default: pymupdf)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="revisit low-confidence sets with an LLM (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument(
        "--summary", action="store_true", help="print a human-readable summary instead of JSON"
    )
    return parser


def format_summary(result) -> str:
    sets = len(result.hardware_sets)
    lines = [
        f"{result.source}  -  {sets} set{'' if sets == 1 else 's'}, "
        f"{result.page_count} page{'' if result.page_count == 1 else 's'}"
    ]
    if result.legend:
        lines.append(f"  legend: {result.legend}")
    for hardware_set in result.hardware_sets:
        pages = sorted({s.page for s in hardware_set.location.spans}) or [hardware_set.location.page]
        marker = " [NOT USED]" if hardware_set.not_used else ""
        lines.append(
            f"\n  SET {hardware_set.set_number}{marker}  pages {pages}  "
            f"confidence {hardware_set.confidence}"
        )
        if hardware_set.description:
            lines.append(f"    {hardware_set.description}")
        for component in hardware_set.components:
            lines.append(
                f"      {str(component.qty or '-'):>3}  {component.description or '':<34}"
                f"{component.catalog_number or '':<26}{component.mfr or '':<6}"
                f"{component.finish or '':<8}{component.notes or ''}"
            )
    for warning in result.warnings:
        lines.append(f"\n  ! {warning}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.pdf.exists():
        print(f"No such file: {args.pdf}", file=sys.stderr)
        return 2

    result = extract_hardware_sets(args.pdf, backend=args.backend, use_llm=args.llm)

    if args.summary:
        print(format_summary(result))
        return 0

    payload = result.model_dump(mode="json")
    text = json.dumps(payload, separators=(",", ":")) if args.compact else json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out} ({len(result.hardware_sets)} hardware sets)", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
