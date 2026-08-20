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
    ],
)
def test_non_headers_are_rejected(text):
    assert match_set_header(line(text)) is None


def test_continuation_header_is_flagged():
    matched = match_set_header(line("HARDWARE GROUP 4 (CONT'D)"))
    assert matched == ("4", None, True)


def test_column_header_line_detection():
    assert is_column_header_line(line("QTY UNIT DESCRIPTION CATALOG NUMBER FINISH MFR"))
    assert is_column_header_line(line("MFG QTY ITEM PRODUCT NO FIN REMARKS"))
    assert not is_column_header_line(line("3 EA HINGE TA2714 US26D MK"))


def test_legend_extraction_splits_multiple_pairs_on_one_line():
    legend = extract_legend([line("MK = MCKINNEY SCH = SCHLAGE PE = PEMKO")])
    assert legend == {"MK": "MCKINNEY", "SCH": "SCHLAGE", "PE": "PEMKO"}
