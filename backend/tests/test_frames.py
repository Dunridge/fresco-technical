"""Running header/footer removal must not eat real content.

A component row that repeats across pages near a page edge was being stripped
as page furniture, silently deleting it from the set. Found by reviewing a real
specbook: `4 EA BB HINGE (NRP) BBLK` sat at the bottom of a page and vanished.
"""

from hardware_sets.parsing.frames import detect_frame_lines
from hardware_sets.parsing.layout import Document, Line, Page, Word


def line(page: int, index: int, text: str, y: float, x0: float = 72.0) -> Line:
    words, cursor = [], x0
    for token in text.split():
        width = len(token) * 5.1
        words.append(Word(text=token, x0=cursor, y0=y, x1=cursor + width, y1=y + 9))
        cursor += width + 5.1
    return Line(page=page, index=index, words=words)


def spaced(page: int, index: int, cells: list[tuple[float, str]], y: float) -> Line:
    """A row whose cells are far enough apart to read as separate columns."""
    words = []
    for x0, text in cells:
        cursor = x0
        for token in text.split():
            width = len(token) * 5.1
            words.append(Word(text=token, x0=cursor, y0=y, x1=cursor + width, y1=y + 9))
            cursor += width + 5.1
    return Line(page=page, index=index, words=words)


def _document(pages: list[Page]) -> Document:
    return Document(source="test.pdf", pages=pages)


def test_running_header_and_footer_are_stripped():
    pages = [
        Page(
            number=n,
            width=612,
            height=792,
            lines=[
                line(n, 0, f"ABC ELEMENTARY SCHOOL 08 71 00 - {n}", 40),
                line(n, 1, "HARDWARE SET NO. 1", 300),
                line(n, 2, f"DOOR HARDWARE 087100 - {n}", 760),
            ],
        )
        for n in (1, 2, 3)
    ]
    frames = detect_frame_lines(_document(pages))
    assert (1, 0) in frames and (2, 0) in frames
    assert (1, 2) in frames and (2, 2) in frames
    assert (1, 1) not in frames


def test_repeated_component_row_near_a_page_edge_survives():
    """The regression: a common component row is not page furniture."""
    component = [(84.0, "4"), (102.0, "EA"), (136.0, "BB HINGE (NRP)"), (263.0, "BBLK")]
    pages = [
        Page(
            number=n,
            width=612,
            height=792,
            lines=[
                line(n, 0, f"VALOR ACRES BUILDING E 087100 - {n}", 40),
                spaced(n, 1, component, 700),
                line(n, 2, f"DOOR HARDWARE 087100 - {n}", 765),
            ],
        )
        for n in (1, 2, 3)
    ]
    frames = detect_frame_lines(_document(pages))
    assert (1, 1) not in frames, "a component row was stripped as a running footer"
    assert (2, 1) not in frames
    assert (1, 0) in frames and (1, 2) in frames


def test_single_page_documents_strip_nothing():
    page = Page(
        number=1,
        width=612,
        height=792,
        lines=[line(1, 0, "SECTION 08 71 00 - DOOR HARDWARE", 40)],
    )
    assert detect_frame_lines(_document([page])) == set()
