import os
import httpx
import json
 
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "2000"))
 
 
class LLMError(Exception):
    pass
 
 
SYSTEM_PROMPT = """You are a financial document analysis tool. 
Your only job is to analyze SEC filing text and output structured Markdown summaries. You must always produce the full analysis directly from the provided text
never ask for more input, never refuse, never add disclaimers. 
Always fill every section with specific findings from the text.
Your task is to extract and distill the most important information from SEC filing sections for investment professionals.
 
Format your response in clean Markdown with the following sections:
## Executive Summary
(2-3 sentence overview of the most critical takeaways)
 
## Key Risk Categories
(Bullet list of the main risk categories identified)
 
## Material Risks — Detailed Findings
(For each significant risk: a brief heading and 1-2 sentence explanation)
 
## Analyst Notes
(Any noteworthy observations, red flags, or items warranting deeper investigation)"""
 
 
def summarize_section(section_text: str, section_header: str,
                      company_name: str = None, filing_type: str = None) -> str:
    prompt = f"""Please analyze the following section from a SEC filing.
 
**Filing Section:** {section_header or 'Unknown Section'}
**Company:** {company_name or 'Unknown Company'}
**Filing Type:** {filing_type or 'Unknown Filing Type'}
 
---
 
{section_text}
 
---
 
Provide your structured analysis now."""
 
    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "options": {"num_predict": MAX_TOKENS},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
 
    except httpx.ConnectError:
        raise LLMError(
            "Cannot connect to Ollama. Make sure it is running: 'ollama serve'"
        )
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise LLMError(f"Ollama error: {e}")