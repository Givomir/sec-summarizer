import threading
from repository import SummaryRepository
from services.sec_fetcher import (
    fetch_filing, extract_section, extract_metadata,
    SECFetchError, SectionNotFoundError, FilingTooLargeError,
)
from services.llm_service import summarize_section, LLMError


def process_filing(summary_id: int, filing_url: str, db_path: str) -> None:
    repo = SummaryRepository(db_path)
    repo.update_processing(summary_id)
    try:
        raw_text = fetch_filing(filing_url)
        metadata = extract_metadata(raw_text)
        section_header, section_text = extract_section(raw_text, section_key="Item 1A")
        summary_text = summarize_section(
            section_text=section_text,
            section_header=section_header,
            company_name=metadata.get("company_name"),
            filing_type=metadata.get("filing_type"),
        )
        repo.update_completed(
            summary_id=summary_id,
            company_name=metadata.get("company_name"),
            filing_type=metadata.get("filing_type"),
            section_extracted=section_header,
            summary_text=summary_text,
        )
    except (SECFetchError, FilingTooLargeError, SectionNotFoundError, LLMError) as e:
        repo.update_failed(summary_id, error=str(e))
    except Exception as e:
        repo.update_failed(summary_id, error=f"Unexpected error: {e}")


def start_processing_thread(summary_id: int, filing_url: str, db_path: str) -> None:
    thread = threading.Thread(
        target=process_filing,
        args=(summary_id, filing_url, db_path),
        daemon=True,
    )
    thread.start()
