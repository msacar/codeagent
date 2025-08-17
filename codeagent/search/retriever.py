from __future__ import annotations
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
import cocoindex
import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer

from ..pipeline.flow import build_index

_MODEL = None


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        # keep this in sync with your indexing model
        model_name = os.getenv(
            "CODEAGENT_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        _MODEL = SentenceTransformer(model_name)
    return _MODEL


def _embed_query(q: str):
    # SentenceTransformers uses `encode` for embeddings
    # normalize to unit length; pgvector `<=>` uses cosine distance
    vec = _get_model().encode([q], normalize_embeddings=True)[0]
    if isinstance(vec, np.ndarray):
        vec = vec.astype(np.float32)
    return vec.tolist()


def search(pool: ConnectionPool, query: str, top_k: int = 8, lang: str | None = None):
    """
    Strict Aider behavior for identifier lookups:
      • If query looks like a single identifier, rank *definitions* by
        graph (PageRank) + lexical; embeddings not used in the score.
      • Otherwise (natural language), use the existing embedding-first path.
    See: Aider repo-map uses captures + dependency graph + PageRank and a token budget,
    not embedding-first selection.  (Aider docs/blog)
    """

    def is_identifier(q: str) -> bool:
        q = q.strip()
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", q))

    table = cocoindex.utils.get_target_default_name(build_index, "code_chunks")
    qvec = _embed_query(query)
    ident_mode = is_identifier(query)

    if ident_mode:
        tok = query.strip()
        sql = f"""
        WITH base AS (
          SELECT
            id, file, name, lang, symbol_kind, container,
            header, body, start, "end",
            COALESCE(rank, 0.0)                      AS pr
          FROM {table}
          WHERE
            is_def = TRUE
            AND (name ILIKE %s
                 OR file ILIKE %s)
            {"AND lang = %s" if lang else ""}
        ),
        scored AS (
          SELECT *,
            -- lexical boosts
            CASE WHEN lower(name) = lower(%s) THEN 0.70
                 WHEN position(lower(%s) in lower(name)) > 0 THEN 0.35
                 WHEN position(lower(%s) in lower(file)) > 0 THEN 0.15
                 ELSE 0.0 END                        AS lex_boost,
            -- prefer callable defs over type/enum
            CASE WHEN symbol_kind IN ('method','function','constructor') THEN 0.20
                 WHEN symbol_kind IN ('class','interface','module')      THEN 0.05
                 WHEN symbol_kind IN ('type','enum')                     THEN -0.10
                 ELSE 0.0 END                        AS kind_boost
          FROM base
        )
        SELECT
          id, file, name, lang, symbol_kind, container,
          header, body, start, "end",
          -- Strict Aider: graph + lexical; no vec term here
          (lex_boost + kind_boost + (0.25 * pr))      AS score,
          pr AS rank
        FROM scored
        ORDER BY score DESC
        LIMIT %s
        """
        pat = f"%{tok}%"
        params = [pat, pat] + ([lang] if lang else []) + [tok, tok, tok, top_k]
        with pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        # Build result list from rows
        results = [
            dict(
                id=r[0],
                file=r[1],
                name=r[2],
                lang=r[3],
                symbol_kind=r[4],
                container=r[5],
                header=r[6],
                body=r[7],
                start=r[8],
                end=r[9],
                score=r[10],
                rank=r[11],
            )
            for r in rows
        ]

        # Safety net: if nothing scored (or empty), fall back to the vector path
        if results:
            return results
        # else continue to the existing vector-first path below

    # existing vector-first SQL for natural language queries
    filters, params = [], [qvec]
    if lang:
        filters.append("lang = %s")
        params.append(lang)

    tok = (query.split() or [""])[0]
    if len(tok) >= 3:
        filters.append("(name ILIKE %s OR file ILIKE %s)")
        params.extend([f"%{tok}%", f"%{tok}%"])

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(qvec)
    params.append(top_k)

    sql = f"""
    SELECT id, file, name, lang, symbol_kind, container,
           header, body, start, "end",
           1.0 - (embedding <=> %s::vector) AS score, rank
    FROM {table}
    {where}
    ORDER BY (embedding <=> %s::vector) ASC, rank DESC
    LIMIT %s
    """
    with pool.connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [
        dict(
            id=r[0],
            file=r[1],
            name=r[2],
            lang=r[3],
            symbol_kind=r[4],
            container=r[5],
            header=r[6],
            body=r[7],
            start=r[8],
            end=r[9],
            score=r[10],
            rank=r[11],
        )
        for r in rows
    ]
