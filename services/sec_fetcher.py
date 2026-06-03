import re
import httpx
from typing import Optional

SEC_USER_AGENT = "NovaBridge Finance research-tool@novabridge.example.com"
MAX_FILING_SIZE_BYTES = 50 * 1024 * 1024
SECTION_CHAR_LIMIT = 40_000

# Minimum characters after a section header to be considered real content
# (not a TOC entry like "Item 1A. Risk Factors .......... 15")
MIN_SECTION_LENGTH = 200

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


def _extract_candidate(clean: str, match) -> Optional[str]:
    """
    Given a regex match for a section header, extract the text until the
    next major Item heading. Returns None if the extracted text is too short
    (indicates a TOC entry, not real content).
    """
    remaining = clean[match.end():]
    end_match = re.search(r"Item\s+\d+[A-Z]?[\.\s]", remaining, re.IGNORECASE)
    section_text = remaining[: end_match.start()] if end_match else remaining
    section_text = section_text.strip()

    if len(section_text) < MIN_SECTION_LENGTH:
        return None  # TOC entry — skip

    if len(section_text) > SECTION_CHAR_LIMIT:
        section_text = section_text[:SECTION_CHAR_LIMIT] + "\n\n[... truncated for length ...]"

    return section_text


def extract_section(text: str, section_key: str = "Item 1A") -> tuple[str, str]:
    """
    Extract the requested section from a SEC filing.

    Strategy:
    1. Find ALL matches of the section header pattern (not just the first).
    2. For each match, check if the text following it is substantial (> MIN_SECTION_LENGTH).
       TOC entries are short (just a page number); real content is long.
    3. Prefer the first match with substantial content.
    4. Fall back through FALLBACK_ORDER if nothing found.
    5. Last resort: return the full cleaned document.
    """
    clean = _clean_text(text)
    keys_to_try = [section_key] + [k for k in FALLBACK_ORDER if k != section_key]

    for key in keys_to_try:
        patterns = SECTION_PATTERNS.get(key, [])
        for pattern in patterns:
            matches = list(re.finditer(pattern, clean, re.IGNORECASE))
            if not matches:
                continue

            # Try each match in order — first one with real content wins
            for m in matches:
                candidate = _extract_candidate(clean, m)
                if candidate is not None:
                    return m.group(0).strip(), candidate

    # Last resort: return full document
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

    if not metadata["company_name"]:
        m = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
        if m:
            metadata["company_name"] = m.group(1).strip()

    return metadata


def _clean_text(text: str) -> str:
    # Remove style and script blocks entirely
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", " ", text)
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
