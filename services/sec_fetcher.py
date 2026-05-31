import re
import httpx
from typing import Optional

SEC_USER_AGENT = "NovaBridge Finance research-tool@novabridge.example.com"
MAX_FILING_SIZE_BYTES = 50 * 1024 * 1024
SECTION_CHAR_LIMIT = 40_000

SECTION_PATTERNS = {
    "Item 1A": [
        r"Item\s+1A[\.\s]*Risk\s+Factors",
        r"ITEM\s+1A[\.\s]*RISK\s+FACTORS",
    ],
    "Item 1": [
        r"Item\s+1[\.\s]*Business",
        r"ITEM\s+1[\.\s]*BUSINESS",
    ],
    "Item 7": [
        r"Item\s+7[\.\s]*Management",
        r"ITEM\s+7[\.\s]*MANAGEMENT",
    ],
}

# Fallback order — try these in sequence if the primary section is missing
FALLBACK_ORDER = ["Item 1A", "Item 1", "Item 7"]


class SECFetchError(Exception):
    pass

class SectionNotFoundError(Exception):
    pass

class FilingTooLargeError(Exception):
    pass


def fetch_filing(url: str) -> str:
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True,
                          headers={"User-Agent": SEC_USER_AGENT}) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise SECFetchError(f"SEC EDGAR returned HTTP {e.response.status_code} for URL: {url}") from e
    except httpx.RequestError as e:
        raise SECFetchError(f"Network error while fetching filing: {e}") from e

    if len(response.content) > MAX_FILING_SIZE_BYTES:
        raise FilingTooLargeError(f"Filing too large: {len(response.content):,} bytes")

    return response.text


def extract_section(text: str, section_key: str = "Item 1A") -> tuple[str, str]:
    """
    Try to extract the requested section. If not found, fall back through
    FALLBACK_ORDER. If nothing matches, return the full cleaned text.
    """
    clean = _clean_text(text)

    # Try the requested section first, then fallbacks
    keys_to_try = [section_key] + [k for k in FALLBACK_ORDER if k != section_key]

    for key in keys_to_try:
        patterns = SECTION_PATTERNS.get(key, [])
        for pattern in patterns:
            m = re.search(pattern, clean, re.IGNORECASE)
            if m:
                header_found = m.group(0).strip()
                remaining = clean[m.end():]
                end_match = re.search(r"Item\s+\d+[A-Z]?[\.\s]", remaining, re.IGNORECASE)
                section_text = remaining[: end_match.start()] if end_match else remaining
                section_text = section_text.strip()

                if len(section_text) > SECTION_CHAR_LIMIT:
                    section_text = section_text[:SECTION_CHAR_LIMIT] + "\n\n[... truncated for length ...]"

                return header_found, section_text

    # Last resort: return the full document text
    full_text = clean[:SECTION_CHAR_LIMIT]
    if len(clean) > SECTION_CHAR_LIMIT:
        full_text += "\n\n[... truncated for length ...]"

    return "Full Document (no standard sections found)", full_text


def extract_metadata(text: str) -> dict:
    metadata: dict[str, Optional[str]] = {"company_name": None, "filing_type": None}

    m = re.search(r"COMPANY CONFORMED NAME:\s*(.+)", text, re.IGNORECASE)
    if m:
        metadata["company_name"] = m.group(1).strip()

    m = re.search(r"CONFORMED SUBMISSION TYPE:\s*(.+)", text, re.IGNORECASE)
    if m:
        metadata["filing_type"] = m.group(1).strip()

    # Fallback: HTML title
    if not metadata["company_name"]:
        m = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
        if m:
            metadata["company_name"] = m.group(1).strip()

    return metadata


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()