"""Column classification decides mfr vs finish from the column, not the value."""

import pytest

from hardware_sets.classification.columns import Column, classify_columns
from hardware_sets.models import Field_


def column(values, index=0, x0=0.0, header=None):
    col = Column(index=index, x0=x0, x1=x0 + 40, raw_x0=x0, raw_x1=x0 + 40, values=values)
    col.header_label = header
    return col


def test_ambiguous_code_reads_as_manufacturer_among_manufacturers():
    columns = [column(["PE", "VON", "LCN", "PE", "PE"], 0, 0.0)]
    classify_columns(columns)
    assert columns[0].field_ is Field_.MFR


def test_same_code_reads_as_finish_among_finishes():
    columns = [column(["PE", "628", "BSP", "PE", "US26D"], 0, 0.0)]
    classify_columns(columns)
    assert columns[0].field_ is Field_.FINISH


def test_no_reads_as_manufacturer_beside_other_manufacturers():
    columns = [column(["HAG", "SAR", "NO", "IVE"], 0, 0.0)]
    classify_columns(columns)
    assert columns[0].field_ is Field_.MFR


def test_manufacturer_and_finish_columns_separate():
    columns = [
        column(["3", "1", "1"], 0, 0.0),
        column(["HINGE", "STOREROOM LOCK", "SURFACE CLOSER"], 1, 60.0),
        column(["MK", "SCH", "LCN"], 2, 200.0),
        column(["US26D", "626", "689"], 3, 260.0),
    ]
    classify_columns(columns)
    assert [c.field_ for c in columns] == [
        Field_.QTY,
        Field_.DESCRIPTION,
        Field_.MFR,
        Field_.FINISH,
    ]


def test_content_overrides_a_misleading_header_label():
    columns = [
        column(["US26D", "626", "689", "630"], 0, 0.0, header="MFR"),
        column(["MK", "SCH", "LCN", "IVE"], 1, 60.0, header="FINISH"),
    ]
    classify_columns(columns)
    assert columns[0].field_ is Field_.FINISH
    assert columns[1].field_ is Field_.MFR


def test_page_legend_resolves_an_all_ambiguous_column():
    columns = [column(["PE", "PE", "PE"], 0, 0.0)]
    classify_columns(columns, legend={"PE": "PEMKO"})
    assert columns[0].field_ is Field_.MFR


def test_page_legend_can_point_the_other_way():
    columns = [column(["PC", "PC", "PC"], 0, 0.0)]
    classify_columns(columns, legend={"PC": "PRIME COAT"})
    assert columns[0].field_ is not Field_.MFR


@pytest.mark.parametrize(
    "values",
    [[], [""], ["", "", ""], ["   ", "\t"]],
)
def test_empty_columns_do_not_crash_the_scorers(values):
    """A column with no content turned up on real specbooks and divided by zero."""
    columns = [column(values, 0, 0.0)]
    classify_columns(columns)
    assert columns[0].field_ is Field_.UNKNOWN


def test_mixed_empty_and_filled_columns_classify():
    columns = [
        column(["", "", ""], 0, 0.0),
        column(["3", "1", "1"], 1, 60.0),
        column(["HINGE", "LOCK", "CLOSER"], 2, 120.0),
    ]
    classify_columns(columns)
    assert columns[1].field_ is Field_.QTY
    assert columns[2].field_ is Field_.DESCRIPTION


def test_handing_codes_do_not_outvote_finishes_in_a_column():
    """A real schedule mixed LHR/RHR with C32D/630; the column is finishes."""
    columns = [column(["LHR", "RHR", "RHR", "C32D", "630", "630"], 0, 0.0)]
    classify_columns(columns)
    assert columns[0].field_ is Field_.FINISH
