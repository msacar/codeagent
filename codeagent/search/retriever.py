from __future__ import annotations

import os
import math
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Literal, Optional, Dict

import psycopg
from psycopg.rows import dict_row

# Optional deps (only used when enabled):
# - SentenceTransformers for local BGE encode
# - voyageai for remote Voyage encode
# - FlagEmbedding for reranker
_BGE_AVAILABLE = False
_VOYAGE_AVAILABLE = False
_RERANK_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _BGE_AVAILABLE = True
except Exception:
    pass

try:
    import voyageai  # type: ignore
    _VOYAGE_AVAILABLE = True
except Exception:
    pass

try:
    from FlagEmbedding import FlagReranker  # type: ignore
    _RERANK_AVAILABLE = True
except Exception:
    pass


# -----------------------------
# Configuration via environment
# -----------------------------
# One model per DB. If you change these, reindex.
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "bge").lower()  # "bge" | "voyage"
EMBED_MODEL = os.getenv("EMBED_MODEL") or (
    "BAAI/bge-code-v1" if EMBED_PROVIDER == "bge" else "voyage-code-3"
)

# Dimensions: bge-code-v1 = 1536; Voyage defaults to 1024 unless you pick a 1536 model.
# (Voyage docs: default 1024; see their model list.)
EMBED_DIM = int(os.getenv("EMBED_DIM") or (1536 if EMBED_PROVIDER == "bge" else 1024))

# Reranker
ENABLE_RERANK = os.getenv("RERANK", "0") in ("1", "true", "True")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")  # multilingual, strong for code/text

# DB
PG_DSN = os.getenv("COCOINDEX_DATABASE_URL")
TABLE = os.getenv("RETRIEVER_TABLE", "codeindex__code_chunks")  # your existing table
EMBED_COL = os.getenv("RETRIEVER_EMBED_COL", "embedding")        # single embed column
TEXT_COL = os.getenv("RETRIEVER_TEXT_COL", "text")               # used for lexical + rerank
ID_COL = os.getenv("RETRIEVER_ID_COL", "id")

# Hybrid recall knobs
VEC_TOPK = int(os.getenv("RETRIEVER_VEC_TOPK", "100"))
LEX_TOPK = int(os.getenv("RETRIEVER_LEX_TOPK", "100"))
MERGE_K  = int(os.getenv("RETRIEVER_MERGE_K", "200"))

# Expansion knobs
EXPAND_DEPS = os.getenv("RETRIEVER_EXPAND_DEPS", "1") in ("1","true","True")
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
    score: float              # larger is better (we normalize cosine distance -> similarity)
    file: Optional[str]
    lang: Optional[str]
    name: Optional[str]
    symbol_kind: Optional[str]
    header: Optional[str]
    body: Optional[str]

# -----------------------------
# Embedding providers
# -----------------------------
_bge_model: Optional[SentenceTransformer] = None
_voyage_client: Optional["voyageai.Client"] = None
_reranker: Optional[FlagReranker] = None


def _lazy_init_bge() -> SentenceTransformer:
    global _bge_model
    if _bge_model is None:
        if not _BGE_AVAILABLE:
            raise RuntimeError("SentenceTransformers not installed for BGE provider.")
        # fp16 on cuda/mps if available
        import torch
        use_fp16 = torch.cuda.is_available() or (getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        _bge_model = SentenceTransformer(
            EMBED_MODEL,
            trust_remote_code=True,
            model_kwargs={"dtype": torch.float16} if use_fp16 else {}
        )
    return _bge_model


def _lazy_init_voyage() -> "voyageai.Client":
    global _voyage_client
    if _voyage_client is None:
        if not _VOYAGE_AVAILABLE:
            raise RuntimeError("`voyageai` package not installed for Voyage provider.")
        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY is not set.")
        _voyage_client = voyageai.Client(api_key=api_key)
    return _voyage_client


def _lazy_init_reranker() -> FlagReranker:
    global _reranker
    if _reranker is None:
        if not _RERANK_AVAILABLE:
            raise RuntimeError("FlagEmbedding not installed for reranker.")
        # Default to fp16 if possible
        _reranker = FlagReranker(RERANK_MODEL, use_fp16=True)
    return _reranker


def _embed_nl_query(text: str) -> List[float]:
    """
    Natural-language query mode.
    - BGE: prepend instruction per FlagEmbedding docs.
    - Voyage: plain text; provider handles prompt internally.
    """
    if EMBED_PROVIDER == "bge":
        m = _lazy_init_bge()
        q = f"{BGE_QUERY_PREFIX}\n{text}".strip()
        vec = m.encode([q], normalize_embeddings=True)[0]
        return vec.tolist()
    elif EMBED_PROVIDER == "voyage":
        client = _lazy_init_voyage()
        # Voyage embeddings API: remote vector of (typically) 1024/1536 dims.
        resp = client.embeddings.create(model=EMBED_MODEL, input=[text])
        return resp.data[0].embedding  # list[float]
    else:
        raise RuntimeError(f"Unknown EMBED_PROVIDER={EMBED_PROVIDER}")


def _embed_code_anchor(code: str) -> List[float]:
    """Code→code mode: no instruction, feed the snippet directly."""
    if EMBED_PROVIDER == "bge":
        m = _lazy_init_bge()
        vec = m.encode([code], normalize_embeddings=True)[0]
        return vec.tolist()
    elif EMBED_PROVIDER == "voyage":
        client = _lazy_init_voyage()
        resp = client.embeddings.create(model=EMBED_MODEL, input=[code])
        return resp.data[0].embedding
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
# <=> is the pgvector distance operator; with COSINE/HNSW index this is fast for ANN.

# Simple lexical path via pg_trgm similarity (fast and easy to add). Enable extension + GIN index:
#   CREATE EXTENSION IF NOT EXISTS pg_trgm;
#   CREATE INDEX IF NOT EXISTS code_chunks_text_gin ON codeindex__code_chunks USING GIN (text gin_trgm_ops);
# (pg_trgm docs).
LEX_SQL = f"""
    SELECT {ID_COL} AS id, file, lang, name, symbol_kind, header, body,
           similarity({TEXT_COL}, %(q)s) AS sim
    FROM {TABLE}
    WHERE {TEXT_COL} % %(q)s
    ORDER BY similarity({TEXT_COL}, %(q)s) DESC
    LIMIT %(k)s
"""

# Neighbor expansion: pull more chunks that share file or names in deps/text
# (minimal, pragmatic expansion — you can swap to your defs/refs graph when you persist it).
EXPAND_SQL = f"""
    SELECT c.{ID_COL} AS id, c.file, c.lang, c.name, c.symbol_kind, c.header, c.body
    FROM {TABLE} c
    WHERE c.file = ANY(%(files)s)
       OR EXISTS (
            SELECT 1
            FROM {TABLE} d
            WHERE d.{ID_COL} = ANY(%(seed_ids)s)
              AND (c.text ILIKE '%%' || d.name || '%%' OR c.name = d.name)
       )
    LIMIT %(limit)s
"""


def _connect() -> psycopg.Connection:
    if not PG_DSN:
        raise RuntimeError("COCOINDEX_DATABASE_URL is not set.")
    return psycopg.connect(PG_DSN, row_factory=dict_row)


def _vec_hits(conn: psycopg.Connection, qvec: List[float], k: int) -> List[Hit]:
    # psycopg3 will adapt Python lists to pgvector automatically if pgvector is installed
    rows = conn.execute(VEC_SQL, {"qvec": qvec, "k": k}).fetchall()
    return [
        Hit(
            id=r["id"], score=float(r["sim"]), file=r.get("file"),
            lang=r.get("lang"), name=r.get("name"), symbol_kind=r.get("symbol_kind"),
            header=r.get("header"), body=r.get("body"),
        )
        for r in rows
    ]


def _lex_hits(conn: psycopg.Connection, q: str, k: int) -> List[Hit]:
    rows = conn.execute(LEX_SQL, {"q": q, "k": k}).fetchall()
    return [
        Hit(
            id=r["id"], score=float(r["sim"]), file=r.get("file"),
            lang=r.get("lang"), name=r.get("name"), symbol_kind=r.get("symbol_kind"),
            header=r.get("header"), body=r.get("body"),
        )
        for r in rows
    ]


def _merge_hits(vec: List[Hit], lex: List[Hit], k: int) -> List[Hit]:
    # Normalize to [0,1], then RRF-style combine
    def _norm(xs: List[float]) -> Dict[str, float]:
        if not xs:
            return {}
        lo, hi = min(xs), max(xs)
        span = max(1e-6, hi - lo)
        return {"_": 0.0, "lo": lo, "span": span}

    vec_scores = {h.id: h.score for h in vec}
    lex_scores = {h.id: h.score for h in lex}

    vnorm = _norm(list(vec_scores.values()))
    lnorm = _norm(list(lex_scores.values()))

    all_ids = list({*vec_scores.keys(), *lex_scores.keys()})
    fused: Dict[str, float] = {}

    for i, hid in enumerate(all_ids, start=1):
        vs = (vec_scores.get(hid, 0.0) - vnorm.get("lo", 0.0)) / max(1e-6, vnorm.get("span", 1.0))
        ls = (lex_scores.get(hid, 0.0) - lnorm.get("lo", 0.0)) / max(1e-6, lnorm.get("span", 1.0))
        # RRF-ish: favor consensus; tweak weights to taste
        fused[hid] = 0.6 * vs + 0.4 * ls

    # reconstruct hits with the better metadata (prefer vec-row if available)
    meta: Dict[str, Hit] = {}
    for h in vec + lex:
        if h.id not in meta:
            meta[h.id] = h

    ranked = sorted(all_ids, key=lambda x: fused[x], reverse=True)[:k]
    return [Hit(id=i, score=fused[i], file=meta[i].file, lang=meta[i].lang, name=meta[i].name,
                symbol_kind=meta[i].symbol_kind, header=meta[i].header, body=meta[i].body) for i in ranked]


def _expand(conn: psycopg.Connection, seeds: List[Hit], limit: int) -> List[Hit]:
    if not seeds:
        return []
    files = list({h.file for h in seeds if h.file})
    seed_ids = [h.id for h in seeds]
    rows = conn.execute(EXPAND_SQL, {"files": files, "seed_ids": seed_ids, "limit": limit}).fetchall()
    extra: List[Hit] = [
        Hit(id=r["id"], score=0.0, file=r.get("file"), lang=r.get("lang"), name=r.get("name"),
            symbol_kind=r.get("symbol_kind"), header=r.get("header"), body=r.get("body"))
        for r in rows if r["id"] not in seed_ids
    ]
    # Keep order as seeds first, then extras
    return seeds + extra


def _maybe_rerank(query_text: str, hits: List[Hit], topn: int = 100) -> List[Hit]:
    if not ENABLE_RERANK or not hits:
        return hits
    rer = _lazy_init_reranker()
    pool = hits[:topn]
    pairs = [(query_text, (h.header or "") + "\n" + (h.body or "")) for h in pool]
    # FlagEmbedding inference returns relevance scores (higher = better).
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
      - mode="nl": natural language task (uses BGE query instruction; Voyage plain).
      - mode="code": code-anchor snippet (no instruction).
    Pipeline:
      1) embed query
      2) vector ANN via pgvector(HNSW)
      3) lexical via pg_trgm (hybrid recall)
      4) fuse -> optional neighbor expansion
      5) optional rerank with bge-reranker-v2-m3
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
