import os
import httpx

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "llama3.2")
MAX_TOKENS      = int(os.environ.get("MAX_TOKENS", "2000"))


class LLMError(Exception):
    pass


SYSTEM_PROMPT = """You are a financial document analysis tool specializing in SEC regulatory filings.
Your task is to extract and summarize key information from SEC filing sections for investment professionals.

Guidelines:
- Base your analysis strictly on the provided source text — do not infer or add information not present in the document
- State uncertainty clearly if a section is incomplete or truncated
- This summary is for informational purposes only and does not constitute investment advice

Format your response in clean Markdown with the following sections:

## Executive Summary
(2-3 sentence overview of the most critical takeaways from the source text)

## Key Risk Categories
(Bullet list of the main risk categories identified in the filing)

## Material Risks - Detailed Findings
(For each significant risk: a brief heading and 1-2 sentence explanation grounded in the source text)

## Analyst Notes
(Noteworthy observations, red flags, or items warranting deeper investigation)

## Source & Limitations
(State which section was analyzed, how many characters were processed, and any extraction limitations)"""


def summarize_section(section_text: str, section_header: str,
                      company_name: str = None, filing_type: str = None) -> str:
    prompt = f"""Analyze the following section from a SEC filing and produce a structured summary grounded strictly in the source text.

**Filing Section:** {section_header or 'Unknown Section'}
**Company:** {company_name or 'Unknown Company'}
**Filing Type:** {filing_type or 'Unknown Filing Type'}
**Characters in section:** {len(section_text):,}

---

{section_text}

---

Provide your structured analysis now. Base all findings strictly on the text above."""

    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "options": {"num_predict": MAX_TOKENS},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    except httpx.ConnectError:
        raise LLMError("Cannot connect to Ollama. Make sure it is running: ollama serve")
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise LLMError(f"Ollama error: {e}")