# Development Notes — SEC Filing Summarizer

**Project:** Automated SEC Filing Summarizer for NovaBridge Finance  
**Developer:** Givomir  
**AI Assistant:** Claude (claude.ai, claude-sonnet-4-6)  
**Date:** May 2026  

---

## Project Overview

Built a full-stack proof-of-concept tool that automates the extraction and summarization of SEC EDGAR filings for financial analysts. The tool accepts a filing URL, fetches the document, extracts the **Item 1A — Risk Factors** section, summarizes it using an LLM, and persists the result in a database with a polling-based UI.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (UI)                       │
│              frontend/index.html                     │
│   POST /api/v1/summaries → poll GET every 3s        │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP
┌───────────────────▼─────────────────────────────────┐
│                Flask API (app.py)                    │
│   POST /api/v1/summaries  → 202 Accepted            │
│   GET  /api/v1/summaries  → paginated list           │
│   GET  /api/v1/summaries/{id} → single result       │
│   GET  /health            → health check             │
└──────┬──────────────────────────┬───────────────────┘
       │ Repository               │ Background Thread
┌──────▼──────────┐    ┌──────────▼──────────────────┐
│   SQLite DB     │    │      processor.py            │
│  (database.py   │    │  1. fetch_filing()           │
│  repository.py) │    │  2. extract_section()        │
│                 │    │  3. summarize_section()       │
│  filing_        │    │  4. repo.update_completed()  │
│  summaries      │    └──────────┬───────────────────┘
│  table          │               │
└─────────────────┘    ┌──────────▼───────────────────┐
                       │    LLM Service                │
                       │  (Ollama locally /            │
                       │   BART on HF Spaces)          │
                       └──────────────────────────────┘
```

---

## Technology Choices & Rationale

### Backend: Flask

Chose Flask over FastAPI because:
- Less boilerplate for a proof-of-concept
- No async complexity needed — background threading handles the long operations
- Simpler to reason about and explain in an interview

**Production consideration:** FastAPI would be preferred for a production system — native async, automatic OpenAPI docs, better type safety.

### Database: SQLite

Chose SQLite over PostgreSQL because:
- Zero infrastructure — no Docker, no connection strings, no setup
- Built into Python — no additional dependencies
- Perfectly adequate for a single-instance prototype
- `sqlite3` context manager with rollback gives safe transaction handling

**Production consideration:** PostgreSQL with SQLAlchemy + Alembic migrations for a multi-instance deployment.

### Async Processing: threading.Thread

Chose daemon threads over Celery/RQ because:
- SEC filings can be several MB and LLM summarization takes 30-60 seconds
- Synchronous processing would cause HTTP timeouts
- `threading.Thread` is the simplest solution with zero additional infrastructure
- Returns 202 Accepted immediately; client polls for status

**Production consideration:** Celery + Redis for fault-tolerant job queues — daemon threads lose in-progress jobs on server restart.

### Repository Pattern

Isolated all database queries in `repository.py`:
- Route handlers stay thin — only HTTP parsing and response formatting
- Data layer is independently testable without touching Flask
- Clean separation: if we switch from SQLite to PostgreSQL, only `repository.py` changes

### LLM Integration

Three providers were evaluated during development:

| Provider | Outcome | Reason |
|---|---|---|
| Anthropic API | Evaluated | Requires paid credits |
| OpenAI API | Tested, rejected | Free tier quota exceeded |
| Ollama + Llama 3.2 | Used locally | Free, private, no rate limits |
| HuggingFace BART | Used on HF Spaces | Free, deployable without GPU |

**Prompt engineering iteration:**  
First system prompt caused the model to refuse financial analysis. Reframed from "financial advisor" to "document analysis tool" — this removed the refusal behavior while producing structured, specific output.

---

## SEC EDGAR Parsing

### Challenges Encountered

**Challenge 1: File format**  
Expected `.txt` files — Apple and most modern filers use `.htm`. Added HTML tag stripping with `re.sub()` before regex matching.

**Challenge 2: Table of Contents false matches**  
`.htm` filings have a clickable table of contents where "Item 1A. Risk Factors" appears as a link. Our regex matched the TOC entry instead of the actual section content (which was only 1 character long).

**Fix:** Use `re.finditer()` to find all matches, iterate in reverse, skip matches where extracted text is shorter than `MIN_SECTION_LENGTH`.

**Challenge 3: Style/script block pollution**  
After stripping HTML tags, inline `<style>` and `<script>` blocks left CSS and JavaScript text in the cleaned output. BART then hallucinated summaries based on CSS class names.

**Fix:** Remove `<style>` and `<script>` blocks entirely before tag stripping:
```python
text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
```

**Challenge 4: Non-standard filings (Form C-U, 8-K)**  
Not all filings have Item 1A. Added a fallback chain: Item 1A → Item 1 → Item 7 → full document text.

---

## Deployment: Hugging Face Spaces

### Why HF Spaces
- Free CPU compute with Docker SDK
- Free access to HuggingFace models (no API key)
- Public URL shareable immediately after deployment
- No credit card required

### Deployment Issues & Fixes

**Issue 1:** `GET /` returned 404  
`send_from_directory` failed to resolve path inside Docker container.  
**Fix:** `send_file(os.path.join(os.path.dirname(__file__), "frontend", "index.html"))`

**Issue 2:** "Could not reach the backend"  
Frontend had `const API_BASE = "http://localhost:5000/api/v1"` hardcoded.  
**Fix:** Changed to relative URL `const API_BASE = "/api/v1"`

**Issue 3:** GitHub Push Protection blocked push  
A real OpenAI API key was committed in `example.env` during an earlier iteration.  
**Fix:** `git rm --cached example.env` + `git commit --amend` + force push

### HF Spaces Configuration

```yaml
# README.md front matter (required by HF)
---
title: SEC Filing Summarizer
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
```

---

## Test Suite

**17 tests across 2 files — all passing**

### test_sec_fetcher.py (unit tests — no network, no LLM)

| Test | What it verifies |
|---|---|
| `test_extract_section_item1a` | Item 1A is extracted correctly and doesn't bleed into next section |
| `test_extract_section_item1` | Item 1 extraction works |
| `test_extract_section_fallback` | Falls back to Item 1 when Item 1A is missing |
| `test_extract_section_full_document_fallback` | Returns full document when no standard sections found |
| `test_extract_section_unknown_key_falls_back` | Unknown section key handled gracefully |
| `test_extract_metadata` | Parses COMPANY CONFORMED NAME and SUBMISSION TYPE |
| `test_extract_metadata_missing` | Returns None gracefully when metadata is absent |
| `test_clean_text_strips_sgml` | HTML/SGML tags removed correctly |
| `test_clean_text_strips_style_blocks` | `<style>` blocks removed entirely |
| `test_section_truncation` | Sections over SECTION_CHAR_LIMIT are truncated |

### test_api.py (integration tests — real SQLite temp DB, LLM mocked)

| Test | What it verifies |
|---|---|
| `test_health` | GET /health returns 200 with status ok |
| `test_submit_missing_url` | POST without url returns 400 |
| `test_submit_invalid_url` | POST with non-http URL returns 400 |
| `test_submit_success` | Valid POST returns 202 with job ID |
| `test_get_not_found` | GET /summaries/9999 returns 404 |
| `test_list_empty` | GET /summaries on empty DB returns total=0 |
| `test_list_and_get` | Submitted job appears in list and is retrievable by ID |

---

## API Reference

| Method | Endpoint | Description | Response |
|---|---|---|---|
| `GET` | `/health` | Health check | `{"status": "ok"}` |
| `POST` | `/api/v1/summaries` | Submit filing URL | `202 Accepted + job ID` |
| `GET` | `/api/v1/summaries` | List all summaries | Paginated list |
| `GET` | `/api/v1/summaries/{id}` | Get single summary | Summary object |

### Job Status Flow

```
pending → processing → completed
                    ↘ failed
```

### Example Request

```bash
curl -X POST http://localhost:5000/api/v1/summaries \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"}'

# Response:
{
  "id": 1,
  "status": "pending",
  "message": "Filing submitted (job ID: 1). Poll GET /api/v1/summaries/1 for status."
}
```

---

## Known Limitations

1. **Company name extraction** — `.htm` filings don't contain the EDGAR header block (`COMPANY CONFORMED NAME:`), so company name shows the filename instead of the legal name
2. **BART summarization quality** — BART is a summarization model, not an instruction-following LLM. Summaries are less structured than Llama 3.2 output
3. **No authentication** — required before any production deployment
4. **In-process threading** — jobs are lost if the server restarts mid-processing
5. **Single-instance only** — SQLite doesn't support concurrent writers across multiple processes

---

## File Structure

```
sec-summarizer/
├── app.py                        # Flask entry point (HF Spaces)
├── main.py                       # Flask entry point (local)
├── database.py                   # SQLite init and connection context manager
├── repository.py                 # Data access layer
├── services/
│   ├── __init__.py
│   ├── sec_fetcher.py            # EDGAR fetch + section extraction
│   ├── llm_service.py            # LLM wrapper (BART / Ollama)
│   └── processor.py             # Background thread orchestrator
├── frontend/
│   └── index.html               # Single-page UI (no build step)
├── tests/
│   ├── __init__.py
│   ├── test_api.py              # Flask integration tests
│   └── test_sec_fetcher.py      # Parsing unit tests
├── docs/
│   ├── development-notes.md     # This document
│   └── ai-conversation-history.json
├── Dockerfile                   # HF Spaces Docker build
├── README.md                    # Setup and usage instructions
├── requirements.txt
├── .env.example
├── .gitignore
└── pytest.ini
```
