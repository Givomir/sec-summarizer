# SEC Filing Summarizer

Automated extraction and summarization of SEC EDGAR filings for financial analysts, built for NovaBridge Finance.

**Live Demo:** [huggingface.co/spaces/Givomir/sec-summarizer](https://huggingface.co/spaces/Givomir/sec-summarizer)

---

## What It Does

1. Analyst pastes a SEC EDGAR filing URL
2. The tool fetches the document and extracts **Item 1A — Risk Factors**
3. An LLM generates a structured analyst summary
4. Result is persisted in SQLite and displayed in the UI with status polling

## Architecture

```
Browser (frontend/index.html)
        │ POST /api/v1/summaries → poll GET /api/v1/summaries/{id}
        ▼
Flask API (main.py)
        │ returns 202 immediately
        │ starts background thread
        ▼
processor.py
        ├── sec_fetcher.py   → fetch + extract section from EDGAR
        ├── llm_service.py   → summarize via Ollama / BART
        └── repository.py    → persist to SQLite
```

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Flask | Lightweight, minimal boilerplate for PoC |
| Database | SQLite | Zero-config, no Docker required |
| Async | `threading.Thread` | Returns 202 immediately; avoids HTTP timeouts |
| LLM (local) | Ollama + Llama 3.2 | Free, private, no API key |
| LLM (cloud) | BART-large-CNN | Free HuggingFace model, no GPU needed |
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

```bash
cp .env.example .env
# Default values work out of the box with Ollama
```

### Run

```bash
python main.py
# Open frontend/index.html in your browser
```

### Test

```bash
pytest -v
# 17 tests — all passing
```

## API Reference

| Method | Endpoint | Description | Response |
|---|---|---|---|
| `GET` | `/health` | Health check | `{"status": "ok"}` |
| `POST` | `/api/v1/summaries` | Submit filing URL | `202 + job ID` |
| `GET` | `/api/v1/summaries` | List all summaries | Paginated list |
| `GET` | `/api/v1/summaries/<id>` | Get single summary | Summary object |

### Job Status Flow

```
pending → processing → completed
                    ↘ failed
```

### Example

```bash
curl -X POST http://localhost:5000/api/v1/summaries \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"}'
```

## Sample Filing URLs

| Company | Type | URL |
|---|---|---|
| Apple | 10-K 2023 | `https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm` |
| Tesla | 10-K 2023 | `https://www.sec.gov/Archives/edgar/data/1318605/000131860524000013/tsla-20231231.htm` |

## Known Limitations

- **Company name** — `.htm` filings don't include the EDGAR header block, so company name shows the filename instead of the legal name
- **BART summarization** — less structured than instruction-following LLMs (Llama, GPT); used only for the free cloud demo
- **Threading** — in-process threads lose jobs on server restart; production needs Celery + Redis
- **Single instance** — SQLite doesn't support concurrent writers across multiple processes
- **Regex parsing** — works for ~90% of EDGAR filings; edge cases (unusual formatting, very old filings) may fail

## Production Considerations

| Component | PoC Choice | Production Choice |
|---|---|---|
| Database | SQLite | PostgreSQL + SQLAlchemy + Alembic |
| Job queue | threading.Thread | Celery + Redis |
| LLM | Ollama / BART | GPT-4o / Claude via API |
| SEC parsing | Regex | Dedicated EDGAR parser + chunking |
| Auth | None | OAuth2 / API keys |
| Observability | None | Structured logging + Sentry |

## AI Assistant Usage

Built with **Claude (claude.ai)**. Full conversation history in `docs/ai-conversation-history.json`.

AI was used for: scaffolding, Flask routes, SQLite repository pattern, regex patterns, prompt engineering, test structure, Dockerfile, and HF Spaces deployment.

All architectural decisions, debugging against real EDGAR filings, and prompt tuning were done by the developer.

> **Disclaimer:** Summaries are generated for informational purposes only and do not constitute investment advice.
