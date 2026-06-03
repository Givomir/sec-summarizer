# SEC Filing Summarizer

Automated extraction and summarization of SEC EDGAR filings for financial analysts, built for NovaBridge Finance.

**Live Demo:** [huggingface.co/spaces/Givomir/sec-summarizer](https://huggingface.co/spaces/Givomir/sec-summarizer)

---

## What It Does

1. Analyst pastes a SEC EDGAR filing URL (.htm or .txt format)
2. The tool fetches the document, cleans HTML, and extracts **Item 1A - Risk Factors**
3. An LLM generates a structured analyst summary grounded in the source text
4. Result is persisted in SQLite and displayed in the UI with status polling

## Architecture

```
Browser (frontend/index.html)
        |  POST /api/v1/summaries -> poll GET /api/v1/summaries/{id}
        v
Flask API (main.py)
        |  returns 202 immediately
        |  starts background thread
        v
processor.py
        |-- sec_fetcher.py   -> fetch + extract section from EDGAR
        |-- llm_service.py   -> summarize via Ollama (local)
        +-- repository.py    -> persist to SQLite
```

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Flask | Lightweight, minimal boilerplate for PoC |
| Database | SQLite | Zero-config, no Docker required |
| Async | `threading.Thread` | Returns 202 immediately; avoids HTTP timeouts |
| LLM | Ollama + Llama 3.2 | Free, private, no API key needed |
| Frontend | Plain HTML/CSS/JS | No build step required |

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) with `llama3.2` model

### Install

```bash
git clone https://github.com/Givomir/sec-summarizer.git
cd sec-summarizer
pip install -r requirements.txt
ollama pull llama3.2
```

### Configure

Create a `.env` file (all defaults work out of the box with Ollama):

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
MAX_TOKENS=2000
DATABASE_PATH=sec_summaries.db
PORT=5000
```

### Run

```bash
python main.py
# Open frontend/index.html in your browser
```

### Test

```bash
pytest -v
# 12 tests -- all passing
```

## Filing URL Formats

EDGAR filings come in two formats:

| Format | Example | Notes |
|---|---|---|
| `.htm` | `aapl-20230930.htm` | Modern filings; HTML with inline styles. Metadata (company name, filing type) must be extracted from HTML title tag. |
| `.txt` | `0000320193-23-000106.txt` | Full submission text file; contains EDGAR header with `COMPANY CONFORMED NAME` and `CONFORMED SUBMISSION TYPE` -- metadata is available automatically. May be very large (10MB+). |

Both formats are supported. `.htm` is more commonly linked from EDGAR search results.

## Sample Filing URLs

| Company | Type | URL |
|---|---|---|
| Apple | 10-K 2023 (.htm) | `https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm` |
| Tesla | 10-K 2023 (.htm) | `https://www.sec.gov/Archives/edgar/data/1318605/000131860524000013/tsla-20231231.htm` |

Find more filings at [EDGAR Full Text Search](https://efts.sec.gov/LATEST/search-index?forms=10-K)

## API Reference

| Method | Endpoint | Description | Response |
|---|---|---|---|
| `GET` | `/health` | Health check | `{"status": "ok"}` |
| `POST` | `/api/v1/summaries` | Submit filing URL | `202 + job ID` |
| `GET` | `/api/v1/summaries` | List all summaries | Paginated list |
| `GET` | `/api/v1/summaries/<id>` | Get single summary | Summary object |

### Job Status Flow

```
pending -> processing -> completed
                     \-> failed
```

### Example

```bash
curl -X POST http://localhost:5000/api/v1/summaries \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"}'

# Response:
# {"id": 1, "status": "pending", "message": "Filing submitted (job ID: 1)..."}

# Poll for result:
curl http://localhost:5000/api/v1/summaries/1
```

## Known Limitations

- **Company name** - `.htm` filings don't include the EDGAR header block, so company name shows the filename instead of the legal name. Use `.txt` format to get metadata automatically.
- **TOC extraction** - Fixed: the extractor now skips Table of Contents entries (which match section headers but contain only page numbers) and finds the first match with substantial content (>200 characters).
- **Threading** - In-process threads lose jobs on server restart; production needs Celery + Redis.
- **Single instance** - SQLite doesn't support concurrent writers across multiple processes.
- **Regex parsing** - Works for ~90% of EDGAR filings; very old or non-standard filings may require a dedicated parser.

## Production Considerations

| Component | PoC Choice | Production Choice |
|---|---|---|
| Database | SQLite | PostgreSQL + SQLAlchemy + Alembic |
| Job queue | threading.Thread | Celery + Redis |
| LLM | Ollama + Llama 3.2 | GPT-4o / Claude via API |
| SEC parsing | Regex + MIN_SECTION_LENGTH guard | Dedicated EDGAR parser + chunking |
| Auth | None | OAuth2 / API keys |
| Observability | None | Structured logging + Sentry |
| Security | None | SSRF protection on URL input, input sanitization |

## AI Assistant Usage

Built with **Claude (claude.ai)**. Full conversation history in `ai-conversation-history.json`.

AI was used for: scaffolding, Flask routes, SQLite repository pattern, regex patterns, prompt engineering, test structure, and deployment configuration.

All architectural decisions, debugging against real EDGAR filings, and prompt tuning were done by the developer.

> **Disclaimer:** Summaries are generated for informational purposes only and do not constitute investment advice.
