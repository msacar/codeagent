from __future__ import annotations
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
import cocoindex

from ..pipeline.flow import build_index


def _embed_query(q: str):
    return cocoindex.functions.SentenceTransformerEmbed(
        model="sentence-transformers/all-MiniLM-L6-v2"
    ).eval(q)


def search(pool: ConnectionPool, query: str, top_k: int = 8, lang: str | None = None):
    table = cocoindex.utils.get_target_default_name(build_index, "code_chunks")
    qvec = _embed_query(query)

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
           1.0 - (embedding <=> %s) AS score, rank
    FROM {table}
    {where}
    ORDER BY (embedding <=> %s) ASC, rank DESC
    LIMIT %s
    """
    with pool.connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(
        id=r[0], file=r[1], name=r[2], lang=r[3], symbol_kind=r[4], container=r[5],
        header=r[6], body=r[7], start=r[8], end=r[9], score=r[10], rank=r[11]
    ) for r in rows]
