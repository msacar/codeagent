import os
import json
import hashlib
import requests
import cocoindex

OLLAMA_URL = os.getenv("CODEAGENT_SUMMARY_URL", "http://localhost:11434/api/generate")
MODEL = os.getenv("CODEAGENT_SUMMARY_MODEL", "qwen3:4b")
TIMEOUT = float(os.getenv("CODEAGENT_SUMMARY_TIMEOUT_SEC", "30"))
MAX_OUT_TOK = int(os.getenv("CODEAGENT_SUMMARY_MAX_TOKENS", "256"))
TEMP = float(os.getenv("CODEAGENT_SUMMARY_TEMPERATURE", "0"))


def _chunk_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


# JSON şemamız: tek satırlık özet + güvenilir alanlar (capabilities, identifiers, lines, confidence)
SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "capabilities": {"type": "array", "items": {"type": "string"}},
        "identifiers": {"type": "array", "items": {"type": "string"}},
        "evidence_lines": {"type": "array", "items": {"type": "integer"}},
        "confidence": {"type": "number"},
    },
    "required": ["summary"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are a precise code summarizer. Output STRICT JSON only. "
    "One-sentence summary in active voice, mention effects (IO/side-effects), "
    "list key capabilities & notable identifiers; cite a few evidence line numbers."
)

PROMPT_TEMPLATE = """Summarize this code chunk for NL retrieval:

FILE: {file}
SPAN: L{start}-L{end}
HEADER:
{header}

BODY:
{body}

Instructions:
- Keep 'summary' under ~28 words if possible.
- 'capabilities' should be repo-specific functions this code accomplishes (e.g., 'http.cache_header', 's3.cache_control', 'url_resolver').
- 'identifiers' = important names found here (funcs, types, consts).
- 'evidence_lines' = a few line numbers within the SPAN that justify the summary.
- 'confidence' in [0,1].
"""


@cocoindex.op.function()
def summarize_chunk(
    text: str, header: str, body: str, file: str, start: int, end: int
) -> str:
    """
    Returns JSON string:
      {"summary": str, "capabilities": [..], "identifiers":[..], "evidence_lines":[..], "confidence": float,
       "content_sha": <sha256 of text>}
    """
    content = text or (header + "\n" + (body or ""))
    content_sha = _chunk_sha(content)

    payload = {
        "model": MODEL,
        "prompt": SYSTEM
        + "\n\n"
        + PROMPT_TEMPLATE.format(
            file=file, start=start, end=end, header=header or "", body=body or ""
        ),
        "format": SCHEMA,  # structured JSON output
        "stream": False,
        "options": {"temperature": TEMP, "num_predict": MAX_OUT_TOK},
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        # Ollama generate returns {"response": "...json..."} body
        raw = data.get("response", "").strip()
        # best-effort parse
        out = json.loads(raw)
    except Exception:
        # minimal fallback: no crash, return dummy structure
        out = {
            "summary": "",
            "capabilities": [],
            "identifiers": [],
            "evidence_lines": [],
            "confidence": 0.0,
        }

    out["content_sha"] = content_sha
    return json.dumps(out, ensure_ascii=False)


@cocoindex.op.function()
def extract_summary_field(summary_json: str, key: str) -> str:
    try:
        obj = json.loads(summary_json or "{}")
        val = obj.get(key, "")
        # return JSON for arrays to keep CocoIndex typing flexible
        if isinstance(val, (list, dict)):
            return json.dumps(val, ensure_ascii=False)
        return str(val)
    except Exception:
        return ""  # safe default
