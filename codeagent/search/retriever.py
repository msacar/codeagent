from __future__ import annotations

import os
import math
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Literal, Optional, Dict

import psycopg
from psycopg.rows import dict_row

# Optional deps (only used when enabled):
# - SentenceTransformers for local BGE encode
# - FlagEmbedding for BGE cross-encoder reranker
# - requests for Voyage REST (required if EMBED_PROVIDER/RERANK_PROVIDER = "voyage")
_BGE_AVAILABLE = False
_RERANK_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _BGE_AVAILABLE = True
except Exception:
    pass

try:
    from FlagEmbedding import FlagReranker  # type: ignore
    _RERANK_AVAILABLE = True
except Exception:
    pass

try:
    import requests  # type: ignore
except Exception as e:  # hard error here only when voyage is requested later
    requests = None  # defer failure until actually used


# -----------------------------
# Configuration via environment
# -----------------------------
# One model per DB. If you change these, reindex.
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "bge").lower()  # "bge" | "voyage"
EMBED_MODEL = os.getenv("EMBED_MODEL") or (
    "BAAI/bge-code-v1" if EMBED_PROVIDER == "bge" else "voyage-code-3"
)

# Dimensions: bge-code-v1 = 1536; Voyage-code-3 default = 1024 (can be 256/512/1024/1536/2048 depending on model)
EMBED_DIM = int(os.getenv("EMBED_DIM") or (1536 if EMBED_PROVIDER == "bge" else 1024))

# Reranker
ENABLE_RERANK = os.getenv("RERANK", "0") in ("1", "true", "True")
# Which provider powers rerank? "flag" (BGE cross-encoder) or "voyage" (REST API)
RERANK_PROVIDER = os.getenv("RERANK_PROVIDER", "flag").lower()
# Default model per provider (override with RERANK_MODEL if you want)
RERANK_MODEL = os.getenv("RERANK_MODEL") or (
    "BAAI/bge-reranker-v2-m3" if RERANK_PROVIDER == "flag" else "rerank-2.5-lite"
)

# Voyage REST
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
VOYAGE_BASE = os.getenv("VOYAGE_BASE", "https://api.voyageai.com/v1")
VOYAGE_TIMEOUT = float(os.getenv("VOYAGE_TIMEOUT", "60"))  # seconds

# DB
PG_DSN = os.getenv("COCOINDEX_DATABASE_URL")
TABLE = os.getenv("RETRIEVER_TABLE", "codeindex__code_chunks")  # your existing table
EMBED_COL = os.getenv("RETRIEVER_EMBED_COL", "embedding")        # single embed column
TEXT_COL = os.getenv("RETRIEVER_TEXT_COL", "text")               # used for lexical + rerank
ID_COL = os.getenv("RETRIEVER_ID_COL", "id")

# Hybrid recall knobs
VEC_TOPK = int(os.getenv("RETRIEVER_VEC_TOPK", "100"))
LEX_TOPK = int(os.getenv("RETRIEVER_LEX_TOPK", "100"))
MERGE_K = int(os.getenv("RETRIEVER_MERGE_K", "200"))
EXPAND_DEPS = os.getenv("RETRIEVER_EXPAND_DEPS", "0") in ("1", "true", "True")
EXPAND_LIMIT = int(os.getenv("RETRIEVER_EXPAND_LIMIT", "100"))

# BGE query instruction for NL queries (recommended by FlagEmbedding):
# “Represent the question for retrieving relevant documents:”
BGE_QUERY_PREFIX = os.getenv(
    "BGE_QUERY_PREFIX",
    "Represent the question for retrieving relevant documents:"
)


@dataclass
class Hit:
    id: str
    score: float              # larger is better (we convert distances -> similarity)
    file: Optional[str]
    lang: Optional[str]
    name: Optional[str]
    symbol_kind: Optional[str]
    header: Optional[str]
    body: Optional[str]


# -----------------------------
# Embedding providers
# -----------------------------
_bge_model: Optional["SentenceTransformer"] = None
_reranker: Optional["FlagReranker"] = None


def _lazy_init_bge() -> "SentenceTransformer":
    global _bge_model
    if _bge_model is None:
        if not _BGE_AVAILABLE:
            raise RuntimeError("SentenceTransformers not installed for BGE provider.")
        # fp16 on cuda/mps if available
        import torch
        use_fp16 = torch.cuda.is_available() or (
            getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        )
        _bge_model = SentenceTransformer(
            EMBED_MODEL,
            trust_remote_code=True,
            device="cuda" if torch.cuda.is_available()
            else ("mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"),
        )
        if use_fp16:
            _bge_model = _bge_model.half()
    return _bge_model


def _lazy_init_reranker() -> "FlagReranker":
    global _reranker
    if _reranker is None:
        if not _RERANK_AVAILABLE:
            raise RuntimeError("FlagEmbedding not installed for reranker.")
        # Default to fp16 if possible
        _reranker = FlagReranker(RERANK_MODEL, use_fp16=True)
    return _reranker


# -----------------------------
# Voyage REST helpers (no SDK)
# -----------------------------
def _check_requests_ready():
    if requests is None:
        raise RuntimeError("`requests` is required for Voyage REST but is not installed.")
    if not VOYAGE_API_KEY:
        raise RuntimeError("VOYAGE_API_KEY is not set for Voyage REST.")


def _voyage_embed_http(texts: List[str], model: str, input_type: str) -> List[List[float]]:
    _check_requests_ready()
    url = f"{VOYAGE_BASE}/embeddings"
    headers = {
        "Authorization": f"Bearer {VOYAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": texts,
        "model": model,
        "input_type": input_type,  # usually "query" for NL; "document" for code/snippets
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=VOYAGE_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # data["data"] is a list of rows with "embedding"
    return [row["embedding"] for row in data["data"]]


def _voyage_rerank_http(query_text: str, docs: List[str], model: str) -> List[Tuple[int, float]]:
    _check_requests_ready()
    url = f"{VOYAGE_BASE}/rerank"
    headers = {
        "Authorization": f"Bearer {VOYAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query_text,
        "documents": docs,
        "model": model,
        "top_k": len(docs),
        # "return_documents": False,  # default; uncomment if you ever want explicit control
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=VOYAGE_TIMEOUT)

    # Raise on HTTP error but keep the server's JSON/body visible
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        try:
            err = resp.json()
        except Exception as ex:
            err = resp.text
            print("here some error occured")
        raise RuntimeError(f"Voyage rerank HTTP {resp.status_code}: {err}") from e

    data = resp.json()
    # REST returns 'data'; SDK examples use 'results'. Support both.
    items = None
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            items = data["data"]
        elif "results" in data and isinstance(data["results"], list):
            items = data["results"]

    if items is None:
        raise RuntimeError(f"Voyage rerank: unexpected payload keys {list(data) if isinstance(data, dict) else type(data)}")

    # Items typically arrive sorted by descending relevance_score; keep order
    out: List[Tuple[int, float]] = []
    for it in items:
        idx = it.get("index")
        score = it.get("relevance_score")
        if idx is None or score is None:
            # Skip malformed entries rather than crashing the whole query
            continue
        out.append((int(idx), float(score)))
    return out


def _embed_nl_query(text: str) -> List[float]:
    """
    Natural-language query mode.
    - BGE: prepend instruction per FlagEmbedding docs.
    - Voyage: REST call; use input_type="query".
    """
    if EMBED_PROVIDER == "bge":
        m = _lazy_init_bge()
        q = f"{BGE_QUERY_PREFIX}\n{text}".strip()
        vec = m.encode([q], normalize_embeddings=True)[0]
        return vec.tolist()
    elif EMBED_PROVIDER == "voyage":
        vecs = _voyage_embed_http([text], model=EMBED_MODEL, input_type="query")
        return vecs[0]
    else:
        raise RuntimeError(f"Unknown EMBED_PROVIDER={EMBED_PROVIDER}")


def _embed_code_anchor(code: str) -> List[float]:
    """Code→code mode: no instruction for BGE; Voyage input_type='document'."""
    if EMBED_PROVIDER == "bge":
        m = _lazy_init_bge()
        vec = m.encode([code], normalize_embeddings=True)[0]
        return vec.tolist()
    elif EMBED_PROVIDER == "voyage":
        vecs = _voyage_embed_http([code], model=EMBED_MODEL, input_type="document")
        return vecs[0]
    else:
        raise RuntimeError(f"Unknown EMBED_PROVIDER={EMBED_PROVIDER}")


# -----------------------------
# Postgres queries
# -----------------------------
VEC_SQL = f"""
    SELECT {ID_COL} AS id, file, lang, name, symbol_kind, header, body,
           1.0 - ({EMBED_COL} <=> %(qvec)s::vector) AS sim
    FROM {TABLE}
    ORDER BY {EMBED_COL} <=> %(qvec)s::vector
    LIMIT %(k)s
"""
# <=> is the pgvector cosine distance operator (with COSINE/HNSW index this is fast).

# Simple lexical path via pg_trgm similarity:
#   CREATE EXTENSION IF NOT EXISTS pg_trgm;
#   CREATE INDEX IF NOT EXISTS code_chunks_text_gin ON codeindex__code_chunks USING GIN (text gin_trgm_ops);
LEX_SQL = f"""
    SELECT {ID_COL} AS id, file, lang, name, symbol_kind, header, body,
           similarity({TEXT_COL}, %(q)s) AS sim
    FROM {TABLE}
    WHERE {TEXT_COL} %% %(q)s
    ORDER BY similarity({TEXT_COL}, %(q)s) DESC
    LIMIT %(k)s
"""

# Neighbor expansion (lightweight): pull more chunks that share file or names in deps/text.
EXPAND_SQL = f"""
    SELECT {ID_COL} AS id, file, lang, name, symbol_kind, header, body
    FROM {TABLE}
    WHERE file = ANY(%(files)s)
      AND {ID_COL} <> ALL(%(seed_ids)s)
    LIMIT %(limit)s
"""


# -----------------------------
# DB helpers
# -----------------------------
def _connect() -> psycopg.Connection:
    if not PG_DSN:
        raise RuntimeError("COCOINDEX_DATABASE_URL is not set.")
    return psycopg.connect(PG_DSN, row_factory=dict_row)


def _vec_hits(conn: psycopg.Connection, qvec: List[float], k: int) -> List[Hit]:
    # psycopg3 will adapt Python lists to pgvector automatically if pgvector is installed
    rows = conn.execute(VEC_SQL, {"qvec": qvec, "k": k}).fetchall()
    return [
        Hit(
            id=r["id"],
            score=float(r["sim"]),
            file=r.get("file"),
            lang=r.get("lang"),
            name=r.get("name"),
            symbol_kind=r.get("symbol_kind"),
            header=r.get("header"),
            body=r.get("body"),
        )
        for r in rows
    ]


def _lex_hits(conn: psycopg.Connection, q: str, k: int) -> List[Hit]:
    rows = conn.execute(LEX_SQL, {"q": q, "k": k}).fetchall()
    return [
        Hit(
            id=r["id"],
            score=float(r["sim"]),
            file=r.get("file"),
            lang=r.get("lang"),
            name=r.get("name"),
            symbol_kind=r.get("symbol_kind"),
            header=r.get("header"),
            body=r.get("body"),
        )
        for r in rows
    ]


def _merge_hits(vec: List[Hit], lex: List[Hit], k: int) -> List[Hit]:
    # Normalize both score streams to [0,1]-ish by min-max over the sample,
    # then fuse with a simple weighted sum (RRF-ish behavior).
    def _norm(xs: Iterable[float]) -> Dict[str, float]:
        xs = list(xs)
        if not xs:
            return {"_": 0.0, "lo": 0.0, "span": 1.0}
        lo, hi = min(xs), max(xs)
        return {"_": 0.0, "lo": lo, "span": max(1e-6, hi - lo)}

    vec_scores = {h.id: h.score for h in vec}
    lex_scores = {h.id: h.score for h in lex}

    vnorm = _norm(list(vec_scores.values()))
    lnorm = _norm(list(lex_scores.values()))

    all_ids = list({*vec_scores.keys(), *lex_scores.keys()})
    fused: Dict[str, float] = {}

    for hid in all_ids:
        vs = (vec_scores.get(hid, 0.0) - vnorm["lo"]) / vnorm["span"]
        ls = (lex_scores.get(hid, 0.0) - lnorm["lo"]) / lnorm["span"]
        fused[hid] = 0.6 * vs + 0.4 * ls

    # reconstruct hits with the better metadata (prefer vec-row if available)
    meta: Dict[str, Hit] = {}
    for h in vec + lex:
        if h.id not in meta:
            meta[h.id] = h

    ranked = sorted(all_ids, key=lambda x: fused[x], reverse=True)[:k]
    return [
        Hit(
            id=i,
            score=fused[i],
            file=meta[i].file,
            lang=meta[i].lang,
            name=meta[i].name,
            symbol_kind=meta[i].symbol_kind,
            header=meta[i].header,
            body=meta[i].body,
        )
        for i in ranked
    ]


def _expand(conn: psycopg.Connection, seeds: List[Hit], limit: int) -> List[Hit]:
    if not seeds:
        return []
    files = list({h.file for h in seeds if h.file})
    seed_ids = [h.id for h in seeds]
    rows = conn.execute(
        EXPAND_SQL, {"files": files, "seed_ids": seed_ids, "limit": limit}
    ).fetchall()

    extra: List[Hit] = [
        Hit(
            id=r["id"],
            score=0.0,
            file=r.get("file"),
            lang=r.get("lang"),
            name=r.get("name"),
            symbol_kind=r.get("symbol_kind"),
            header=r.get("header"),
            body=r.get("body"),
        )
        for r in rows
        if r["id"] not in seed_ids
    ]
    # Keep order as seeds first, then extras
    return seeds + extra


def _maybe_rerank(query_text: str, hits: List[Hit], topn: int = 100) -> List[Hit]:
    if not ENABLE_RERANK or not hits:
        return hits
    pool = hits[:topn]
    texts = [(h.header or "") + "\n" + (h.body or "") for h in pool]
    if RERANK_PROVIDER == "voyage":
        try:
            idx_scores = _voyage_rerank_http(query_text, texts, model=RERANK_MODEL)
            scored = [(pool[i], s) for (i, s) in idx_scores]
            # Already sorted by relevance desc
            return [Hit(**{**h.__dict__, "score": float(s)}) for (h, s) in scored]
        except Exception as e:
            print("[WARN] Voyage rerank failed:", e)
            return pool
    else:
        # default "flag" (BGE CrossEncoder via FlagEmbedding)
        try:
            rer = _lazy_init_reranker()
        except Exception as e:
            print("[WARN] FlagEmbedding reranker unavailable:", e)
            return pool
        pairs = [(query_text, t) for t in texts]
        scores = rer.compute_score(pairs, normalize=True)
        rescored = [Hit(**{**h.__dict__, "score": float(s)}) for h, s in zip(pool, scores)]
        return sorted(rescored, key=lambda x: x.score, reverse=True)


def search_repo(
    query: str,
    mode: Literal["nl", "code"] = "nl",
    vector_topk: int = VEC_TOPK,
    lexical_topk: int = LEX_TOPK,
    merge_k: int = MERGE_K,
    do_expand: bool = EXPAND_DEPS,
    expand_limit: int = EXPAND_LIMIT,
) -> List[Hit]:
    """
    Two modes:
      - mode="nl": natural language task (uses BGE query instruction; Voyage input_type='query').
      - mode="code": code-anchor snippet (no instruction; Voyage input_type='document').
    Pipeline:
      1) embed query
      2) vector ANN via pgvector(HNSW)
      3) lexical via pg_trgm (hybrid recall)
      4) fuse -> optional neighbor expansion
      5) optional rerank (BGE FlagEmbedding or Voyage REST)
    """
    qvec = _embed_nl_query(query) if mode == "nl" else _embed_code_anchor(query)

    with _connect() as conn:
        vec = _vec_hits(conn, qvec, vector_topk)
        lex = _lex_hits(conn, query, lexical_topk)

        fused = _merge_hits(vec, lex, merge_k)

        if do_expand:
            fused = _expand(conn, fused, expand_limit)

        # Final rerank by cross-encoder (if enabled)
        final = _maybe_rerank(query, fused, topn=min(200, len(fused)))
        return final
