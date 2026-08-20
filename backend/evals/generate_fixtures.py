"""Generate the synthetic specbook fixtures used by the evaluation corpus.

The real challenge corpus is not redistributable, so the golden corpus is built
from documents that reproduce the layout families and caveats the challenge
calls out: table schedules, section/list sets, inverted column orders, page
spanning sets, NOT USED sets, missing quantities, wrapped descriptions and the
ambiguous PE / NO codes appearing as a manufacturer on one page and as a finish
on another.

Run:  python evals/generate_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = pymupdf.paper_rect("letter")
MONO = "cour"
MONO_BOLD = "cobo"
SANS_BOLD = "hebo"


class PageBuilder:
    def __init__(self, page: pymupdf.Page, top: float = 60.0, leading: float = 12.0):
        self.page = page
        self.y = top
        self.leading = leading

    def row(self, cells: list[tuple[float, str]], font: str = MONO, size: float = 8.5) -> None:
        for x, text in cells:
            if text:
                self.page.insert_text((x, self.y), text, fontname=font, fontsize=size)
        self.y += self.leading

    def line(self, x: float, text: str, font: str = MONO, size: float = 8.5) -> None:
        self.row([(x, text)], font=font, size=size)

    def blank(self, n: int = 1) -> None:
        self.y += self.leading * n


def _running_header(builder: PageBuilder, project: str, section: str) -> None:
    builder.row([(72, project), (450, section)], font=SANS_BOLD, size=9)
    builder.blank()


def build_fixture_01(path: Path) -> None:
    """Table schedule, explicit header row, FINISH column left of MFR."""
    doc = pymupdf.open()
    cols = {"qty": 72.0, "unit": 100.0, "desc": 132.0, "cat": 280.0, "fin": 440.0, "mfr": 500.0}

    def header_row(b: PageBuilder) -> None:
        b.row(
            [
                (cols["qty"], "QTY"),
                (cols["unit"], "UNIT"),
                (cols["desc"], "DESCRIPTION"),
                (cols["cat"], "CATALOG NUMBER"),
                (cols["fin"], "FINISH"),
                (cols["mfr"], "MFR"),
            ],
            font=MONO_BOLD,
        )

    def comp(b: PageBuilder, qty: str, unit: str, desc: str, cat: str, fin: str, mfr: str) -> None:
        b.row(
            [
                (cols["qty"], qty),
                (cols["unit"], unit),
                (cols["desc"], desc),
                (cols["cat"], cat),
                (cols["fin"], fin),
                (cols["mfr"], mfr),
            ]
        )

    # --- page 1 -------------------------------------------------------------
    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "ABC ELEMENTARY SCHOOL", "08 71 00 - 1")
    b.line(72, "HARDWARE SET NO. 1", font=MONO_BOLD, size=9.5)
    b.line(72, "DOORS: 101, 102, 103A")
    b.blank()
    header_row(b)
    comp(b, "3", "EA", "HINGE", "TA2714 4-1/2 X 4-1/2", "US26D", "MK")
    comp(b, "1", "EA", "STOREROOM LOCK", "L9080P 06A", "626", "SCH")
    comp(b, "1", "EA", "SURFACE CLOSER", "4040XP SCUSH", "689", "LCN")
    comp(b, "1", "EA", "KICK PLATE", "8400 10 X 34", "US32D", "IVE")
    comp(b, "1", "EA", "WALL STOP", "WS406CCV", "US26D", "IVE")
    comp(b, "3", "EA", "SILENCER", "SR64", "GRY", "IVE")
    b.blank(2)

    b.line(72, "HARDWARE SET NO. 2", font=MONO_BOLD, size=9.5)
    b.line(72, "DOORS: 105, 106")
    b.blank()
    header_row(b)
    comp(b, "2", "EA", "CONTINUOUS HINGE", "224HD", "628", "PE")
    comp(b, "1", "EA", "EXIT DEVICE", "99L-06 996L-06", "626", "VON")
    comp(b, "1", "EA", "SURFACE CLOSER", "4040XP RW/PA", "689", "LCN")
    comp(b, "1", "EA", "THRESHOLD", "171A", "AL", "PE")
    comp(b, "1", "SET", "GASKETING", "S88D", "BK", "PE")
    comp(b, "", "EA", "DOOR SWEEP", "315CN", "AL", "PE")

    # --- page 2 -------------------------------------------------------------
    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "ABC ELEMENTARY SCHOOL", "08 71 00 - 2")
    b.line(72, "HARDWARE SET NO. 3", font=MONO_BOLD, size=9.5)
    b.line(72, "NOT USED")
    b.blank(2)

    b.line(72, "HARDWARE SET NO. 4", font=MONO_BOLD, size=9.5)
    b.line(72, "DOORS: 201, 202, 203, 204")
    b.blank()
    header_row(b)
    comp(b, "3", "EA", "HINGE", "TA2714 4-1/2 X 4-1/2", "US26D", "MK")
    comp(b, "1", "EA", "CLASSROOM LOCK", "L9070P 06A", "626", "SCH")
    comp(b, "1", "EA", "ELECTRIFIED MORTISE", "L9092EU 06A", "626", "SCH")
    b.row([(cols["desc"], "LOCK, FAIL SECURE")])

    # --- page 3 : bare continuation of set 4, then set 5 ---------------------
    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "ABC ELEMENTARY SCHOOL", "08 71 00 - 3")
    comp(b, "1", "EA", "OVERHEAD STOP", "100S", "630", "GLY")
    comp(b, "1", "EA", "SURFACE CLOSER", "4040XP REG", "689", "LCN")
    comp(b, "1", "EA", "KICK PLATE", "8400 10 X 34", "US32D", "IVE")
    b.blank(2)

    b.line(72, "HARDWARE SET NO. 5", font=MONO_BOLD, size=9.5)
    b.line(72, "DOORS: 210")
    b.blank()
    header_row(b)
    comp(b, "3", "EA", "HINGE", "TA2714 4-1/2 X 4-1/2", "US26D", "MK")
    comp(b, "1", "EA", "PASSAGE SET", "L9010 06A", "626", "SCH")

    doc.save(path)
    doc.close()


def build_fixture_02(path: Path) -> None:
    """Section/list format, no header row, MFR left of FINISH, PE means a finish."""
    doc = pymupdf.open()
    cols = {"qty": 90.0, "unit": 112.0, "desc": 145.0, "cat": 290.0, "mfr": 440.0, "fin": 490.0}

    def comp(b: PageBuilder, qty: str, unit: str, desc: str, cat: str, mfr: str, fin: str) -> None:
        b.row(
            [
                (cols["qty"], qty),
                (cols["unit"], unit),
                (cols["desc"], desc),
                (cols["cat"], cat),
                (cols["mfr"], mfr),
                (cols["fin"], fin),
            ]
        )

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    b.row([(72, "SECTION 08 71 00 - DOOR HARDWARE")], font=SANS_BOLD, size=10)
    b.blank()

    b.line(72, "HW SET #1 - EXTERIOR ENTRANCE DOORS", font=MONO_BOLD, size=9.5)
    comp(b, "3", "EA", "HINGE", "BB1279 4-1/2 X 4-1/2 NRP", "HAG", "US26D")
    comp(b, "1", "EA", "MORTISE LOCK", "8904 LNL", "SAR", "US26D")
    comp(b, "1", "EA", "SURFACE CLOSER", "1601 SHCUSH", "NO", "689")
    comp(b, "1", "EA", "WALL BUMPER", "406", "IVE", "US26D")
    b.blank(2)

    b.line(72, "HW SET #2A - PAINTED HOLLOW METAL DOORS", font=MONO_BOLD, size=9.5)
    comp(b, "2", "EA", "HINGE", "BB1279 4-1/2 X 4-1/2", "HAG", "PE")
    comp(b, "1", "EA", "PRIVACY SET", "5402LN", "YAL", "628")
    comp(b, "1", "EA", "OVERHEAD HOLDER", "90S", "GLY", "BSP")
    comp(b, "1", "EA", "FLOOR STOP", "441CU", "ROC", "PE")
    b.blank(2)

    b.line(72, "HW SET #3 - NOT USED", font=MONO_BOLD, size=9.5)
    b.blank(2)

    b.line(72, "HW SET #4 - STOREFRONT DOORS", font=MONO_BOLD, size=9.5)
    comp(b, "1", "EA", "CYLINDER, SEE DIVISION", "20-022 ICX", "SCH", "626")
    b.row([(cols["desc"], "28 FOR ACCESS CONTROL WIRING")])
    comp(b, "", "EA", "THRESHOLD", "2005AV", "NGP", "AL")
    comp(b, "1", "SET", "PERIMETER GASKETING", "5050B", "NGP", "BK")

    doc.save(path)
    doc.close()


def build_fixture_03(path: Path) -> None:
    """Third schema: MFR first, a NOTES column, an abbreviation legend and an
    explicit `(CONT'D)` continuation across a page break."""
    doc = pymupdf.open()
    cols = {"mfr": 72.0, "qty": 118.0, "desc": 150.0, "cat": 290.0, "fin": 405.0, "notes": 455.0}

    def header_row(b: PageBuilder) -> None:
        b.row(
            [
                (cols["mfr"], "MFG"),
                (cols["qty"], "QTY"),
                (cols["desc"], "ITEM"),
                (cols["cat"], "PRODUCT NO"),
                (cols["fin"], "FIN"),
                (cols["notes"], "REMARKS"),
            ],
            font=MONO_BOLD,
        )

    def comp(b: PageBuilder, mfr: str, qty: str, desc: str, cat: str, fin: str, notes: str) -> None:
        b.row(
            [
                (cols["mfr"], mfr),
                (cols["qty"], qty),
                (cols["desc"], desc),
                (cols["cat"], cat),
                (cols["fin"], fin),
                (cols["notes"], notes),
            ]
        )

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "RIVERSIDE MEDICAL CENTER", "087100-1")
    b.line(72, "MANUFACTURER ABBREVIATIONS:", font=MONO_BOLD)
    b.row([(72, "MK = MCKINNEY"), (240, "SCH = SCHLAGE"), (400, "PE = PEMKO")])
    b.row([(72, "LCN = LCN CLOSERS"), (240, "IVE = IVES"), (400, "NO = NORTON")])
    b.blank(2)

    b.line(72, "HARDWARE GROUP 3A", font=MONO_BOLD, size=9.5)
    b.line(72, "PROVIDE EACH SINGLE DOOR TO HAVE THE FOLLOWING:")
    header_row(b)
    comp(b, "MK", "3", "HINGE", "T4A3786 4-1/2", "652", "")
    comp(b, "SCH", "1", "OFFICE LOCK", "ND50PD RHO", "626", "SEE NOTE 4")
    comp(b, "NO", "1", "DOOR CLOSER", "7500", "689", "")
    comp(b, "IVE", "", "SILENCER", "SR64", "GRY", "OMIT AT GASKETED")
    b.blank(2)

    b.line(72, "HARDWARE GROUP 4", font=MONO_BOLD, size=9.5)
    b.line(72, "PROVIDE EACH PAIR OF DOORS TO HAVE THE FOLLOWING:")
    header_row(b)
    comp(b, "MK", "6", "HINGE", "T4A3786 4-1/2", "652", "")
    comp(b, "SCH", "1", "EXIT DEVICE", "98EO", "626", "")

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "RIVERSIDE MEDICAL CENTER", "087100-2")
    b.line(72, "HARDWARE GROUP 4 (CONT'D)", font=MONO_BOLD, size=9.5)
    header_row(b)
    comp(b, "LCN", "2", "DOOR CLOSER", "4040XP REG", "689", "")
    comp(b, "PE", "1", "THRESHOLD", "2005AV", "AL", "FIELD CUT")
    b.blank(2)

    b.line(72, "HARDWARE GROUP 5", font=MONO_BOLD, size=9.5)
    b.line(72, "NOT APPLICABLE")

    doc.save(path)
    doc.close()


def build_fixture_04(path: Path) -> None:
    """Held-out stress case, written after the pipeline to test generalisation.

    Manufacturer and finish share a single column, quantity and unit share a
    cell, one set's manufacturer codes are *all* ambiguous, boilerplate prose
    sits between sets, and the page furniture is a footer rather than a header.
    """
    doc = pymupdf.open()
    cols = {"qty": 90.0, "desc": 126.0, "cat": 250.0, "mfrfin": 400.0, "notes": 470.0}

    def comp(b, qty: str, desc: str, cat: str, mfrfin: str, notes: str = "") -> None:
        b.row(
            [
                (cols["qty"], qty),
                (cols["desc"], desc),
                (cols["cat"], cat),
                (cols["mfrfin"], mfrfin),
                (cols["notes"], notes),
            ]
        )

    def footer(b, text: str) -> None:
        b.page.insert_text((430, 720), text, fontname=SANS_BOLD, fontsize=9)

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    b.line(72, "SET #7", font=MONO_BOLD, size=9.5)
    comp(b, "3 EA", "HINGE", "TA2714 4-1/2 X 4-1/2", "MK US26D")
    comp(b, "1 EA", "ENTRANCE LOCK", "L9453P 06A", "SCH 626")
    comp(b, "1 EA", "SURFACE CLOSER", "4040XP EDA", "LCN 689")
    comp(b, "1 EA", "FLOOR STOP", "441CU", "IVE US26D")
    comp(b, "1 SET", "SEALS", "", "ZE BK")
    b.blank()
    b.line(72, "ALL HARDWARE SHALL BE INSTALLED IN ACCORDANCE WITH THE")
    b.line(72, "MANUFACTURERS PRINTED INSTRUCTIONS AND ANSI A156 SERIES.")
    b.blank(2)

    b.line(72, "SET #8 - VESTIBULE DOORS", font=MONO_BOLD, size=9.5)
    comp(b, "2 EA", "HINGE", "BB1168 4-1/2 X 4-1/2", "PE US26D")
    comp(b, "1 EA", "PUSH PLATE", "70C 4 X 16", "PE US32D")
    comp(b, "1 EA", "PULL PLATE", "111X70C", "PE US32D")
    footer(b, "08 71 00 - 5")

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    b.line(72, "SET #9", font=MONO_BOLD, size=9.5)
    b.line(126, "NOT USED")
    b.blank(2)

    b.line(72, "SET #12", font=MONO_BOLD, size=9.5)
    comp(b, "3 EA", "HINGE", "TA714", "MK US26D")
    comp(b, "1 EA", "STOREROOM LOCK", "L9080P 06A", "SCH 626")
    comp(b, "1 EA", "WALL STOP", "WS406CCV", "IVE US26D", "MOUNT AT 42 AFF")
    footer(b, "08 71 00 - 6")

    doc.save(path)
    doc.close()


def build_fixture_05(path: Path) -> None:
    """Set identifier as a *column*, not a header line.

    Modelled on a real specbook family: one continuous table whose leftmost
    column carries the set id, sets delimited by that id changing, and a
    combined `MANUFACTURER - PRODUCT` column. The header row repeats on the
    second page, which previously got stripped as a running header.
    """
    doc = pymupdf.open()
    cols = {"set": 55.0, "type": 150.0, "mfr": 250.0, "qty": 430.0, "fin": 470.0}

    def header_row(b: PageBuilder) -> None:
        b.row(
            [
                (cols["set"], "SET"),
                (cols["type"], "HARDWARE TYPE"),
                (cols["mfr"], "MANUFACTURER - PRODUCT"),
                (cols["qty"], "QTY"),
                (cols["fin"], "FINISH"),
            ],
            font=MONO_BOLD,
        )

    def row(b: PageBuilder, set_id: str, kind: str, product: str, qty: str, fin: str) -> None:
        b.row(
            [
                (cols["set"], set_id),
                (cols["type"], kind),
                (cols["mfr"], product),
                (cols["qty"], qty),
                (cols["fin"], fin),
            ]
        )

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "NORTHSIDE BRANCH LIBRARY", "087100-1")
    header_row(b)
    row(b, "1.1", "CYLINDER", "SCHLAGE - FSIC PRIMUS", "1", "613")
    row(b, "1.2", "MORTISE HINGE", "IVES - 5BB1 4.5", "3", "613")
    row(b, "", "MORTISE LOCKSET", "SCHLAGE - L9077", "1", "613")
    row(b, "", "SURFACE CLOSER", "LCN - 4040XP", "1", "691")
    row(b, "2.1", "CONT HINGE", "IVES - 224HD", "2", "628")
    row(b, "", "EXIT DEVICE", "VON DUPRIN - 99L", "1", "626")

    b = PageBuilder(doc.new_page(width=PAGE.width, height=PAGE.height))
    _running_header(b, "NORTHSIDE BRANCH LIBRARY", "087100-2")
    header_row(b)
    row(b, "", "THRESHOLD", "PEMKO - 171A", "1", "AL")
    row(b, "3.1", "WALL STOP", "IVES - WS406CCV", "1", "626")
    row(b, "", "SILENCER", "IVES - SR64", "3", "GRY")

    doc.save(path)
    doc.close()


BUILDERS = {
    "fixture_01_table_schedule.pdf": build_fixture_01,
    "fixture_02_list_sections.pdf": build_fixture_02,
    "fixture_03_alt_schema.pdf": build_fixture_03,
    "fixture_04_merged_columns.pdf": build_fixture_04,
    "fixture_05_set_column.pdf": build_fixture_05,
}


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, builder in BUILDERS.items():
        target = FIXTURES / name
        builder(target)
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
