"""Vocabulary is evidence only - ambiguous codes must resolve to neither side."""

import pytest

from hardware_sets.classification import vocab


@pytest.mark.parametrize("code", ["MK", "SCH", "LCN", "VON", "IVE", "HAG", "SAR", "NGP"])
def test_known_manufacturer_codes(code):
    assert vocab.looks_like_manufacturer(code)
    assert not vocab.looks_like_finish(code)


@pytest.mark.parametrize("code", ["US26D", "US32D", "626", "630", "689", "652", "BSP", "GRY", "BK"])
def test_known_finish_codes(code):
    assert vocab.looks_like_finish(code)
    assert not vocab.looks_like_manufacturer(code)


@pytest.mark.parametrize("code", ["PE", "NO", "AL", "PC", "BR"])
def test_ambiguous_codes_claim_neither_side(code):
    assert vocab.is_ambiguous_code(code)
    assert not vocab.looks_like_manufacturer(code)
    assert not vocab.looks_like_finish(code)


@pytest.mark.parametrize("value", ["TA2714", "4040XP", "L9080P", "WS406CCV", "20-022"])
def test_catalog_numbers(value):
    assert vocab.looks_like_catalog_number(value)


def test_plain_integers_are_not_catalog_numbers():
    assert not vocab.looks_like_catalog_number("406")


@pytest.mark.parametrize("text", ["NOT USED", "N/A", "NOT APPLICABLE", "NONE", "not used"])
def test_not_used_markers(text):
    assert vocab.is_not_used_marker(text)


def test_composite_finish():
    assert vocab.looks_like_finish("US26D/US32D")
    assert vocab.looks_like_finish("630/626")
