import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.sec_fetcher import extract_section, extract_metadata, _clean_text

SAMPLE_FILING = """
CONFORMED SUBMISSION TYPE: 10-K
COMPANY CONFORMED NAME: ACME CORPORATION

Item 1. Business
This is the business section text.

Item 1A. Risk Factors
Risk factor one: Competition is fierce in our market.
Risk factor two: We rely on a small number of key customers.

Item 1B. Unresolved Staff Comments
Nothing to report here.
"""

SHORT_FILING = """
CONFORMED SUBMISSION TYPE: C-U
COMPANY CONFORMED NAME: SMALL COMPANY INC

This is a progress update with no standard Item sections.
The company raised $500,000 in its crowdfunding campaign.
"""


def test_extract_section_item1a():
    header, text = extract_section(SAMPLE_FILING, "Item 1A")
    assert "Risk Factors" in header
    assert "Competition is fierce" in text
    assert "Unresolved Staff Comments" not in text


def test_extract_section_item1():
    header, text = extract_section(SAMPLE_FILING, "Item 1")
    assert "Business" in header
    assert "business section text" in text


def test_extract_section_fallback():
    """When Item 1A is missing, should fall back to Item 1."""
    filing = "Item 1. Business\nSome business text.\nItem 2. Properties\nMore text."
    header, text = extract_section(filing, "Item 1A")
    assert "Business" in header
    assert "business text" in text


def test_extract_section_full_document_fallback():
    """When no standard sections exist, returns full document text."""
    header, text = extract_section(SHORT_FILING, "Item 1A")
    assert "Full Document" in header
    assert "progress update" in text


def test_extract_section_unknown_key_falls_back():
    """Unknown section key falls back gracefully to full document."""
    header, text = extract_section(SHORT_FILING, "Item 99")
    assert "Full Document" in header


def test_extract_metadata():
    meta = extract_metadata(SAMPLE_FILING)
    assert meta["company_name"] == "ACME CORPORATION"
    assert meta["filing_type"] == "10-K"


def test_extract_metadata_missing():
    meta = extract_metadata("No metadata here.")
    assert meta["company_name"] is None
    assert meta["filing_type"] is None


def test_clean_text_strips_sgml():
    clean = _clean_text("<DOCUMENT>Hello <b>world</b></DOCUMENT>")
    assert "<" not in clean
    assert "Hello" in clean


def test_section_truncation(monkeypatch):
    import services.sec_fetcher as fetcher
    monkeypatch.setattr(fetcher, "SECTION_CHAR_LIMIT", 50)
    long_filing = "Item 1A. Risk Factors\n" + ("X" * 200) + "\nItem 2. Something"
    _, text = extract_section(long_filing, "Item 1A")
    assert "[... truncated for length ...]" in text