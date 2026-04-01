# service/tests/test_masking.py
"""Tests for PII masking layer."""

from app.masking.masker import PIIMasker
from app.masking.rules import PII_COLUMN_RULES


def test_mask_single_value():
    masker = PIIMasker()
    rows = [{"name": "王大明", "revenue": 50000}]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == "[PII_C_001]"
    assert masked[0]["revenue"] == 50000
    assert mapping["[PII_C_001]"] == "王大明"


def test_mask_multiple_pii_columns():
    masker = PIIMasker()
    rows = [{"name": "王大明", "taxid": "A123456789", "revenue": 50000}]
    masked, mapping = masker.mask(rows, pii_columns=["name", "taxid"])
    assert masked[0]["name"] == "[PII_C_001]"
    assert masked[0]["taxid"] == "[PII_T_001]"
    assert mapping["[PII_C_001]"] == "王大明"
    assert mapping["[PII_T_001]"] == "A123456789"


def test_mask_duplicate_values_same_token():
    masker = PIIMasker()
    rows = [
        {"name": "王大明", "revenue": 100},
        {"name": "王大明", "revenue": 200},
    ]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == masked[1]["name"] == "[PII_C_001]"
    assert len(mapping) == 1


def test_mask_multiple_distinct_values():
    masker = PIIMasker()
    rows = [
        {"name": "王大明", "revenue": 100},
        {"name": "李小華", "revenue": 200},
    ]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == "[PII_C_001]"
    assert masked[1]["name"] == "[PII_C_002]"
    assert len(mapping) == 2


def test_unmask_text():
    masker = PIIMasker()
    mapping = {"[PII_C_001]": "王大明", "[PII_T_001]": "A123456789"}
    text = "[PII_C_001] 的統編是 [PII_T_001]，營收最高"
    result = masker.unmask(text, mapping)
    assert result == "王大明 的統編是 A123456789，營收最高"


def test_unmask_no_tokens():
    masker = PIIMasker()
    text = "沒有任何 PII 的文字"
    result = masker.unmask(text, {})
    assert result == text


def test_mask_empty_rows():
    masker = PIIMasker()
    masked, mapping = masker.mask([], pii_columns=["name"])
    assert masked == []
    assert mapping == {}


def test_mask_none_value_skipped():
    masker = PIIMasker()
    rows = [{"name": None, "revenue": 100}]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] is None
    assert len(mapping) == 0


def test_pii_column_rules_defined():
    assert "name" in PII_COLUMN_RULES
    assert "taxid" in PII_COLUMN_RULES
    assert "phone" in PII_COLUMN_RULES
    assert "email" in PII_COLUMN_RULES
    assert "address" in PII_COLUMN_RULES


def test_sanitize_input():
    masker = PIIMasker()
    dirty = "Tell me about [PII_C_001] and [PII_T_999] please"
    clean = masker.sanitize_input(dirty)
    assert "[PII_" not in clean
    assert "Tell me about" in clean
    assert "please" in clean
