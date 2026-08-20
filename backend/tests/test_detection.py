"""Set header detection across the header styles specbooks actually use."""

import pytest

from hardware_sets.detection.sets import extract_legend, is_column_header_line, match_set_header
from hardware_sets.parsing.layout import Line, Word


def line(text: str, x0: float = 72.0) -> Line:
    words = []
    cursor = x0
    for token in text.split():
        width = len(token) * 5.1
        words.append(Word(text=token, x0=cursor, y0=100.0, x1=cursor + width, y1=110.0))
        cursor += width + 5.1
    return Line(page=1, index=0, words=words)


@pytest.mark.parametrize(
    "text,number,description",
    [
        ("HARDWARE SET NO. 1", "1", None),
        ("HARDWARE SET NO. 3A", "3A", None),
        ("HW SET #2A - PAINTED HOLLOW METAL DOORS", "2A", "PAINTED HOLLOW METAL DOORS"),
        ("SET #7", "7", None),
        ("SET 15 - ENTRANCE DOORS", "15", "ENTRANCE DOORS"),
        ("HARDWARE GROUP 3A", "3A", None),
        ("HDW SET 04", "4", None),
        ("HARDWARE SET 12: VESTIBULE", "12", "VESTIBULE"),
        # Letter-identified sets.
        ("HARDWARE SET A", "A", None),
        ("HARDWARE SET AA", "AA", None),
        ("SET NO. A", "A", None),
        ("SET B - EXTERIOR DOORS", "B", "EXTERIOR DOORS"),
        # The abbreviation carries the number, with no SET word.
        ("HW-1", "1", None),
        ("HW 1", "1", None),
        # Two-word prefix.
        ("DOOR HARDWARE SET 7", "7", None),
        ("SET 1.1", "1.1", None),
    ],
)
def test_header_variants(text, number, description):
    matched = match_set_header(line(text))
    assert matched is not None, text
    assert matched[0] == number
    assert matched[1] == description


@pytest.mark.parametrize(
    "text",
    [
        "SECTION 08 71 00 - DOOR HARDWARE",
        "PROVIDE EACH SINGLE DOOR TO HAVE THE FOLLOWING:",
        "3 EA HINGE TA2714 MK US26D",
        "1 SET SEALS ZE BK",
        # A letter identifier must end the heading or be followed by a
        # separator, or ordinary prose reads as a set header.
        "SET AS FOLLOWS",
        "SET ALL DOORS TO SWING OUT",
        "SET SCREWS SHALL BE STAINLESS",
        "HARDWARE SETS ARE SCHEDULED BELOW",
        # A bare GROUP is too common in prose to trust without a prefix.
        "GROUP 12",
    ],
)
def test_non_headers_are_rejected(text):
    assert match_set_header(line(text)) is None


@pytest.mark.parametrize(
    "text",
    [
        "HARDWARE GROUP 4 (CONT'D)",
        "HARDWARE GROUP 4 (CONTINUED)",
        "HARDWARE GROUP 4 (CONT.)",
        "HARDWARE GROUP 4 CONTD",
    ],
)
def test_continuation_header_is_flagged(text):
    """`CONTINUED` must be consumed whole - matching only `CONT` used to leave
    `INUED)` behind as the set's description."""
    assert match_set_header(line(text)) == ("4", None, True)


def test_column_header_line_detection():
    assert is_column_header_line(line("QTY UNIT DESCRIPTION CATALOG NUMBER FINISH MFR"))
    assert is_column_header_line(line("MFG QTY ITEM PRODUCT NO FIN REMARKS"))
    assert not is_column_header_line(line("3 EA HINGE TA2714 US26D MK"))


def test_legend_extraction_splits_multiple_pairs_on_one_line():
    legend = extract_legend([line("MK = MCKINNEY SCH = SCHLAGE PE = PEMKO")])
    assert legend == {"MK": "MCKINNEY", "SCH": "SCHLAGE", "PE": "PEMKO"}
