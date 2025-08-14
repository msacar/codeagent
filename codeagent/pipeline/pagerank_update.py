from __future__ import annotations
from typing import Dict
import networkx as nx
from psycopg_pool import ConnectionPool
import cocoindex

from .flow import build_index


def _load_graph_inputs(pool: ConnectionPool, table: str):
    """
    Load minimal data to build a defs/refs graph:
      - per-chunk: id, file, name, deps(json{name->count})
    We aggregate to:
      - defines[name] -> set(files)
      - refs_by_file[file] -> Counter-like dict{name->count}
    """
    sql = f"""SELECT id, file, name, deps FROM {table}"""
    defines: Dict[str, set] = {}
    refs_by_file: Dict[str, Dict[str, int]] = {}
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            for cid, file, name, deps in cur.fetchall():
                # defs: any chunk with a non-empty name is considered a def chunk
                if name:
                    defines.setdefault(name, set()).add(file)
                # refs: merge dep counts (dict of name->count) per file
                if isinstance(deps, dict):
                    rf = refs_by_file.setdefault(file, {})
                    for n, c in deps.items():
                        if not n:
                            continue
                        rf[n] = rf.get(n, 0) + int(c or 0)
    return defines, refs_by_file


def _compute_file_pagerank(
    defines: Dict[str, set], refs_by_file: Dict[str, Dict[str, int]]
) -> Dict[str, float]:
    """
    Build a file→file weighted graph: for each ref name in a file,
    add edges to all files that define that name.
    """
    G = nx.DiGraph()
    for ref_file, name_counts in refs_by_file.items():
        G.add_node(ref_file)
        for name, cnt in name_counts.items():
            for def_file in defines.get(name, ()):
                if def_file == ref_file:
                    continue
                w = cnt if cnt > 0 else 1
                if G.has_edge(ref_file, def_file):
                    G[ref_file][def_file]["weight"] += w
                else:
                    G.add_edge(ref_file, def_file, weight=w)
    if len(G) == 0:
        return {}
    # Use edge weights; damping 0.85 mirrors common defaults (Aider-like)
    pr = nx.pagerank(G, alpha=0.85, max_iter=200, weight="weight")
    return pr


def _update_chunk_ranks(
    pool: ConnectionPool, table: str, file_pr: Dict[str, float]
) -> int:
    """
    Write per-file PR scores back onto all chunks from that file.
    """
    if not file_pr:
        return 0
    sql = f"""UPDATE {table} SET rank = %s WHERE file = %s"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            rows = 0
            for f, r in file_pr.items():
                cur.execute(sql, (float(r), f))
                rows += cur.rowcount or 0
    return rows


def update_pagerank(pool: ConnectionPool) -> int:
    """
    Public entry: recompute file PageRank from current chunks and update table.
    Returns number of rows touched by the update.
    """
    table = cocoindex.utils.get_target_default_name(build_index, "code_chunks")
    defines, refs_by_file = _load_graph_inputs(pool, table)
    file_pr = _compute_file_pagerank(defines, refs_by_file)
    return _update_chunk_ranks(pool, table, file_pr)


def top_files_and_symbols(pool: ConnectionPool, top_n: int = 50):
    """
    Convenience for CLI: compute PR, then return:
      - top files by PR
      - top symbols weighted by citing file PR (sum over files of ref_count * PR(file)).
    """
    table = cocoindex.utils.get_target_default_name(build_index, "code_chunks")
    defines, refs_by_file = _load_graph_inputs(pool, table)
    file_pr = _compute_file_pagerank(defines, refs_by_file)

    # Top files
    top_files = sorted(file_pr.items(), key=lambda kv: kv[1], reverse=True)[:top_n]

    # Symbol scores: sum over citing files (ref_count * PR(file))
    sym_score: Dict[tuple[str, str], float] = {}  # (name, def_file) -> score
    for ref_file, name_counts in refs_by_file.items():
        w_file = file_pr.get(ref_file, 0.0)
        if w_file == 0:
            continue
        for name, cnt in name_counts.items():
            for def_file in defines.get(name, ()):
                if def_file == ref_file:
                    continue
                key = (name, def_file)
                sym_score[key] = sym_score.get(key, 0.0) + (cnt * w_file)
    top_syms = sorted(sym_score.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    # return nice shapes
    return top_files, [(n, f, s) for (n, f), s in top_syms]
