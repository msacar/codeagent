# codeagent/commands/repomap.py
import os, re, math, textwrap, json
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
import cocoindex

from ..pipeline.flow import build_index  # table name helper

def _table():
    return cocoindex.utils.get_target_default_name(build_index, "code_chunks")

def _tok_est(s: str) -> int:
    # ~4 chars/token heuristic (close enough for a budget gate)
    return max(1, math.ceil(len(s) / 4))

def _extract_filename_mentions(q: str) -> set[str]:
    # crude but effective: foo/bar/baz.ts, baz.py, etc.
    pat = r"[\w\-/]+?\.[A-Za-z0-9]+"
    return set(re.findall(pat, q or ""))

def _extract_identifier_mentions(q: str) -> set[str]:
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", q or "")
    return set(toks)

def _fetch_defs(pool, lang=None):
    tbl = _table()
    sql = f"""
      SELECT id, file, name, lang, symbol_kind, container,
             header, body, start, "end", COALESCE(rank,0.0) AS pr
      FROM {tbl}
      WHERE is_def = TRUE
        {"AND lang = %s" if lang else ""}
    """
    with pool.connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(sql, ([lang] if lang else []))
            rows = cur.fetchall()
    cols = ["id","file","name","lang","symbol_kind","container","header","body","start","end","pr"]
    return [dict(zip(cols, r)) for r in rows]

def _score_row(row, mentioned_fnames, mentioned_idents, chat_files):
    pr = float(row.get("pr", 0.0))
    # Aider-like bias: boost files mentioned in prompt and files already "in chat".
    boost = 0.0
    if row["file"] in mentioned_fnames:
        boost += 0.35
    if row["file"] in chat_files:
        boost += 0.30
    nm = (row.get("name") or "").lower()
    if any(ident.lower() == nm for ident in mentioned_idents):
        boost += 0.25
    # callable defs slightly preferred (functions/methods)
    kind = (row.get("symbol_kind") or "").lower()
    if kind in ("function","method","constructor"):
        boost += 0.05
    # final score = PR + biases (simple & effective)
    return pr + boost

def _sig_lines(row, max_lines=12):
    # Aider includes "critical lines/signature" for defs; our header holds those.
    head = (row.get("header") or "").strip().splitlines()
    head = [h for h in head if h.strip()]
    return "\n".join(("│" + h) for h in head[:max_lines])

def _group_by_file(rows):
    byf = {}
    for r in rows:
        byf.setdefault(r["file"], []).append(r)
    return byf

def cmd_repomap(args):
    db_url = os.environ["COCOINDEX_DATABASE_URL"]
    pool = ConnectionPool(db_url)

    mentioned_fnames = _extract_filename_mentions(args.q)
    mentioned_idents = _extract_identifier_mentions(args.q)
    chat_files = set(args.chat_file or [])

    # 1) fetch defs (you already have PR computed)
    defs = _fetch_defs(pool, lang=args.lang)

    # 2) score & sort
    scored = [
        ( _score_row(r, mentioned_fnames, mentioned_idents, chat_files), r )
        for r in defs
    ]
    scored.sort(key=lambda t: t[0], reverse=True)

    # 3) group by file in ranked order
    by_file = _group_by_file([r for _, r in scored])
    file_order = sorted(by_file.keys(),
                        key=lambda f: max(_score_row(r, mentioned_fnames, mentioned_idents, chat_files)
                                          for r in by_file[f]),
                        reverse=True)

    # 4) render within token budget (Aider's map-tokens).
    budget = int(args["map_tokens"] if isinstance(args, dict) else args.map_tokens)
    used = 0
    out = []
    hdr = f"# RepoMap (context) for: {args.q}\n"
    out.append(hdr); used += _tok_est(hdr)

    for f in file_order:
        block_hdr = f"\n{f}:\n"
        est = _tok_est(block_hdr)
        if used + est > budget: break
        out.append(block_hdr); used += est

        # keep a small number of defs per file (top by our score)
        defs_in_file = sorted(by_file[f],
                              key=lambda r: _score_row(r, mentioned_fnames, mentioned_idents, chat_files),
                              reverse=True)[:6]
        for r in defs_in_file:
            sig = _sig_lines(r)
            blk = textwrap.dedent(f"""\
            │{r['symbol_kind']} {r.get('name') or ''}  (L{r['start']}-L{r['end']})
{sig}
            """)
            est = _tok_est(blk)
            if used + est > budget: break
            out.append(blk); used += est
        if used >= budget: break

    text = "\n".join(out).rstrip() + "\n"
    with open(args.out, "w", encoding="utf-8") as fp:
        fp.write(text)
    print(f"Wrote {args.out} (~{used} tokens)")
