import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.sec_fetcher import extract_section, extract_metadata, _clean_text

# Realistic filing with Table of Contents followed by real content
SAMPLE_FILING_WITH_TOC = """
CONFORMED SUBMISSION TYPE: 10-K
COMPANY CONFORMED NAME: ACME CORPORATION

TABLE OF CONTENTS

Item 1.   Business ...................... 3
Item 1A.  Risk Factors ................. 15
Item 1B.  Unresolved Staff Comments .... 42

PART I

Item 1. Business

ACME Corporation was founded in 1990 and operates in the technology sector.
We design, manufacture and sell innovative products globally across 40 countries.
We have approximately 10,000 employees worldwide as of fiscal year end.
Our revenue streams are diversified across hardware, software and services segments.

Item 1A. Risk Factors

The following risk factors may materially affect our business, financial condition,
and results of operations. Investors should carefully consider these risks.

Competition Risk: We operate in highly competitive markets with numerous established
players who may have greater resources, brand recognition, and market share than us.
Increased competition could result in price reductions, reduced margins, and loss of
market share that could materially harm our business and results of operations.

Supply Chain Risk: Our business depends on a limited number of suppliers for critical
components. Any disruption due to natural disasters, geopolitical events, or supplier
insolvency could significantly impact our ability to manufacture products on time.

Regulatory Risk: We are subject to extensive government regulations including data
privacy laws, environmental regulations, and trade restrictions. Changes in these
regulations or failure to comply could result in fines, penalties, and reputational
damage that materially affects our financial results and ongoing operations.

Item 1B. Unresolved Staff Comments

None.
"""

# Filing without TOC for simple extraction tests
FILING_ITEM1_ONLY = """
Item 1. Business

This is the business section with enough content to pass the minimum length check.
We operate in multiple markets globally and have diverse revenue streams across regions.
Our products serve customers in over 30 countries across all major continents worldwide.
We employ approximately 5,000 people across our global operations and facilities.

Item 2. Properties

We lease office space in 10 cities.
"""

SHORT_FILING = """
CONFORMED SUBMISSION TYPE: C-U
COMPANY CONFORMED NAME: SMALL COMPANY INC

This is a progress update with no standard Item sections.
The company raised $500,000 in its crowdfunding campaign this quarter.
"""


def test_extract_section_skips_toc_entry():
    """Critical: must return real content, not the TOC page reference."""
    header, text = extract_section(SAMPLE_FILING_WITH_TOC, "Item 1A")
    assert "Risk Factors" in header
    assert len(text) > 200, "Extracted section too short — likely captured TOC entry"
    assert "Competition Risk" in text or "Supply Chain" in text or "Regulatory" in text
    # TOC entry would contain only dots and page numbers
    assert ".......... 15" not in text


def test_extract_section_item1a_with_toc():
    header, text = extract_section(SAMPLE_FILING_WITH_TOC, "Item 1A")
    assert "Risk Factors" in header
    assert "Competition Risk" in text
    assert "Unresolved Staff Comments" not in text


def test_extract_section_item1():
    header, text = extract_section(FILING_ITEM1_ONLY, "Item 1")
    assert "Business" in header
    assert "business section" in text


def test_extract_section_fallback_to_item1():
    """When Item 1A is missing, should fall back to Item 1."""
    header, text = extract_section(FILING_ITEM1_ONLY, "Item 1A")
    assert "Business" in header
    assert "business section" in text


def test_extract_section_full_document_fallback():
    """When no standard sections exist, returns full document text."""
    header, text = extract_section(SHORT_FILING, "Item 1A")
    assert "Full Document" in header
    assert "progress update" in text


def test_extract_section_unknown_key_falls_back():
    header, text = extract_section(SHORT_FILING, "Item 99")
    assert "Full Document" in header


def test_extract_metadata():
    meta = extract_metadata(SAMPLE_FILING_WITH_TOC)
    assert meta["company_name"] == "ACME CORPORATION"
    assert meta["filing_type"] == "10-K"


def test_extract_metadata_missing():
    meta = extract_metadata("No metadata here.")
    assert meta["company_name"] is None
    assert meta["filing_type"] is None


def test_clean_text_strips_html_tags():
    clean = _clean_text("<DOCUMENT>Hello <b>world</b></DOCUMENT>")
    assert "<" not in clean
    assert "Hello" in clean


def test_clean_text_strips_style_blocks():
    dirty = "<style>.foo { color: red; font-size: 12px; }</style>Hello world"
    clean = _clean_text(dirty)
    assert "color" not in clean
    assert "Hello" in clean


def test_clean_text_strips_script_blocks():
    dirty = "<script>var x = 1; alert('hello');</script>Real content here"
    clean = _clean_text(dirty)
    assert "alert" not in clean
    assert "Real content" in clean


def test_section_truncation(monkeypatch):
    import services.sec_fetcher as fetcher
    monkeypatch.setattr(fetcher, "SECTION_CHAR_LIMIT", 100)
    monkeypatch.setattr(fetcher, "MIN_SECTION_LENGTH", 10)
    long_filing = "Item 1A. Risk Factors\n" + ("X" * 500) + "\nItem 2. Something else"
    _, text = extract_section(long_filing, "Item 1A")
    assert "[... truncated for length ...]" in text
