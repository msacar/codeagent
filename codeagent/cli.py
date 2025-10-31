from __future__ import annotations

import os
import sys
import argparse
from typing import List, Optional, Literal

from dotenv import load_dotenv
load_dotenv()

# Optional dependencies used by other subcommands (indexing, etc.)
try:
    from psycopg_pool import ConnectionPool  # noqa: F401
    from pgvector.psycopg import register_vector  # noqa: F401
except Exception:
    pass

# --- Best-effort imports to match your project layout -------------------------
# We try the package (e.g., yourpkg.cli run as module) first, then local files.

run_index = build_index = None
top_files_and_symbols = update_pagerank = None

# flow / pagerank
try:
    from .pipeline.flow import run_index as _run_index, build_index as _build_index  # type: ignore
    run_index, build_index = _run_index, _build_index
except Exception:
    try:
        from flow import run_index as _run_index, build_index as _build_index  # type: ignore
        run_index, build_index = _run_index, _build_index
    except Exception:
        pass

try:
    from .pipeline.pagerank_update import (  # type: ignore
        top_files_and_symbols as _top_files_and_symbols,
        update_pagerank as _update_pagerank,
    )
    top_files_and_symbols, update_pagerank = _top_files_and_symbols, _update_pagerank
except Exception:
    try:
        from pagerank_update import (  # type: ignore
            top_files_and_symbols as _top_files_and_symbols,
            update_pagerank as _update_pagerank,
        )
        top_files_and_symbols, update_pagerank = _top_files_and_symbols, _update_pagerank
    except Exception:
        pass

# retriever (prefer the new `search_repo` name; fall back to `search`)
def _resolve_search_func():
    # pkg path
    try:
        from .search.retriever import search_repo as search  # type: ignore
        return search
    except Exception:
        try:
            from .search.retriever import search as search  # type: ignore
            return search
        except Exception:
            pass
    # local path
    try:
        from retriever import search_repo as search  # type: ignore
        return search
    except Exception:
        try:
            from retriever import search as search  # type: ignore
            return search
        except Exception:
            pass
    raise ImportError(
        "Could not import search function. Expected one of:\n"
        "  - .search.retriever.search_repo\n"
        "  - .search.retriever.search\n"
        "  - retriever.search_repo\n"
        "  - retriever.search"
    )


do_search = _resolve_search_func()


# --- Printing helpers ---------------------------------------------------------

def _format_line_refs(line_refs: Literal["none", "start", "range"], header: Optional[str]) -> str:
    """
    Extract best-effort line refs from header if present.
    Expected patterns like: 'file.ts:L12-34 name(kind)' or similar;
    this keeps the output compact without parsing AST.
    """
    if not header or line_refs == "none":
        return ""
    # Very light heuristic: look for LNUMBER or LNUMBER-LNUMBER
    import re
    m = re.search(r"(L\d+(?:-\d+)?)", header)
    return f" [{m.group(1)}]" if m else ""


def _print_hits(hits, k: int, line_refs: Literal["none", "start", "range"]) -> None:
    if not hits:
        print("No results.")
        return
    for i, h in enumerate(hits[:k], 1):
        file_part = h.file or "(unknown file)"
        lr = _format_line_refs(line_refs, h.header)
        name = h.name or ""
        kind = f" ({h.symbol_kind})" if getattr(h, "symbol_kind", None) else ""
        print(f"{i:>2}. {file_part}{lr} :: {name}{kind}  — score={h.score:.4f}")
        # Compact preview (first line of header/body)
        head = (h.header or "").strip().splitlines()[:1]
        body = (h.body or "").strip().splitlines()[:2]
        for ln in head:
            print(f"      H: {ln[:180]}")
        for ln in body:
            print(f"      B: {ln[:180]}")
        if head or body:
            print()


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("cocoindex-cli", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    # ---------------- query ----------------
    q = sub.add_parser("query", help="Hybrid search over codebase (vector + lexical) with optional rerank.")
    q.add_argument("--q", "--query", dest="query", required=True, help="Query string (NL) or code snippet (use --mode code).")
    q.add_argument("-k", "--topk", type=int, default=20, help="How many final results to print.")

    # Retrieval & rerank options
    rgrp = q.add_argument_group("retrieval & rerank options")
    rgrp.add_argument("--mode", choices=["nl", "code"], default=os.getenv("RETRIEVER_MODE", "nl"),
                      help="Query mode: natural language (nl) or code anchor (code).")
    rgrp.add_argument("--embed-provider", choices=["bge", "voyage"], default=os.getenv("EMBED_PROVIDER", "bge"),
                      help="Embedding provider to use for queries.")
    rgrp.add_argument("--embed-model", default=os.getenv("EMBED_MODEL"),
                      help="Embedding model name (defaults depend on provider).")
    rgrp.add_argument("--rerank", action="store_true",
                      default=os.getenv("RERANK", "0") in ("1", "true", "True"),
                      help="Enable cross-encoder reranking of the fused shortlist.")
    rgrp.add_argument("--rerank-provider", choices=["flag", "voyage"], default=os.getenv("RERANK_PROVIDER", "flag"),
                      help="Reranker provider: 'flag' (BGE cross-encoder) or 'voyage' (API).")
    rgrp.add_argument("--rerank-model", default=os.getenv("RERANK_MODEL"),
                      help="Reranker model (e.g., BAAI/bge-reranker-v2-m3, rerank-2.5-lite).")
    rgrp.add_argument("--vec-topk", type=int, default=int(os.getenv("RETRIEVER_VEC_TOPK", "100")),
                      help="Vector ANN candidates to retrieve before fusion.")
    rgrp.add_argument("--lex-topk", type=int, default=int(os.getenv("RETRIEVER_LEX_TOPK", "100")),
                      help="Lexical (trigram) candidates to retrieve before fusion.")
    rgrp.add_argument("--merge-k", type=int, default=int(os.getenv("RETRIEVER_MERGE_K", "200")),
                      help="How many items to keep after hybrid fusion.")
    rgrp.add_argument("--expand-deps", action="store_true",
                      default=os.getenv("RETRIEVER_EXPAND_DEPS", "0") in ("1", "true", "True"),
                      help="Expand with same-file neighbors to avoid missing call sites.")
    rgrp.add_argument("--expand-limit", type=int, default=int(os.getenv("RETRIEVER_EXPAND_LIMIT", "100")),
                      help="Max extra neighbors when expanding.")

    # Output options
    ogrp = q.add_argument_group("output options")
    ogrp.add_argument("--line-refs", choices=["none", "start", "range"], default="range",
                      help="Show file line refs if present in headers.")
    ogrp.add_argument("--map-tokens", type=int, default=None,
                      help="Soft budget for downstream consumers (only printed as stats).")
    ogrp.add_argument("--loi-hilite", action="store_true",
                      help="(UI hint) Highlight anchor lines in condensed bodies.")
    ogrp.add_argument("--loi-mark", default="▶ ", help="Marker for highlighted lines (UI hint).")

    # ---------------- index ----------------
    ix = sub.add_parser("index", help="Parse, chunk, embed, and write to Postgres.")
    ix.add_argument("--watch", action="store_true", help="Watch the repo and rebuild incrementally (if supported).")

    # ---------------- pagerank ----------------
    pr = sub.add_parser("pagerank", help="Update PageRank and print top files/symbols.")
    pr.add_argument("--topn", type=int, default=20, help="How many to print from the top lists.")

    return p


def _apply_env_from_args(args: argparse.Namespace) -> None:
    """
    Export retrieval/rerank configuration to environment so lower layers
    (retriever.py) don't need argparse imports.
    """
    # Retrieval/rerank env switches
    if getattr(args, "mode", None):
        os.environ["RETRIEVER_MODE"] = args.mode
    if getattr(args, "embed_provider", None):
        os.environ["EMBED_PROVIDER"] = args.embed_provider
    if getattr(args, "embed_model", None):
        os.environ["EMBED_MODEL"] = args.embed_model
    if getattr(args, "rerank", None) is not None:
        os.environ["RERANK"] = "1" if args.rerank else "0"
    if getattr(args, "rerank_provider", None):
        os.environ["RERANK_PROVIDER"] = args.rerank_provider
    if getattr(args, "rerank_model", None):
        os.environ["RERANK_MODEL"] = args.rerank_model
    if getattr(args, "vec_topk", None) is not None:
        os.environ["RETRIEVER_VEC_TOPK"] = str(args.vec_topk)
    if getattr(args, "lex_topk", None) is not None:
        os.environ["RETRIEVER_LEX_TOPK"] = str(args.lex_topk)
    if getattr(args, "merge_k", None) is not None:
        os.environ["RETRIEVER_MERGE_K"] = str(args.merge_k)
    if getattr(args, "expand_deps", None) is not None:
        os.environ["RETRIEVER_EXPAND_DEPS"] = "1" if args.expand_deps else "0"
    if getattr(args, "expand_limit", None) is not None:
        os.environ["RETRIEVER_EXPAND_LIMIT"] = str(args.expand_limit)

    # UI/printing hints for downstream tools (optional)
    if getattr(args, "map_tokens", None) is not None:
        os.environ["CODEAGENT_MAP_TOKENS"] = str(args.map_tokens)
    if getattr(args, "loi_hilite", None):
        os.environ["CODEAGENT_LOI_HILITE"] = "1"
    if getattr(args, "loi_mark", None):
        os.environ["CODEAGENT_LOI_MARK"] = args.loi_mark


def cmd_query(args: argparse.Namespace) -> int:
    load_dotenv()

    _apply_env_from_args(args)

    # Execute search
    mode: Literal["nl", "code"] = args.mode
    fused_hits = do_search(
        query=args.query,
        mode=mode,  # retriever supports "nl" and "code"
        vector_topk=int(os.getenv("RETRIEVER_VEC_TOPK", "100")),
        lexical_topk=int(os.getenv("RETRIEVER_LEX_TOPK", "100")),
        merge_k=int(os.getenv("RETRIEVER_MERGE_K", "200")),
        do_expand=os.getenv("RETRIEVER_EXPAND_DEPS", "0") in ("1", "true", "True"),
        expand_limit=int(os.getenv("RETRIEVER_EXPAND_LIMIT", "100")),
    )

    _print_hits(fused_hits, args.topk, args.line_refs)

    # Optional context stats (for downstream token budgets)
    if args.map_tokens:
        total_chars = 0
        for h in fused_hits[: args.topk]:
            file_len = len(h.file or "")
            header_len = len(h.header or "")
            body_len = len(h.body or "")
            total_chars += file_len + header_len + body_len
        approx_tokens = total_chars // 4
        print("\n📊 Context Statistics:")
        print(f"  Items included: {min(args.topk, len(fused_hits))}")
        print(f"  Approx tokens used: {approx_tokens}/{args.map_tokens}")

    return 0


def cmd_index(args: argparse.Namespace) -> int:
    load_dotenv()
    if run_index is None:
        print("Indexing pipeline is not available in this environment.", file=sys.stderr)
        return 2
    if args.watch:
        # If your flow.py exports a watcher-based incremental loop, use it;
        # otherwise just run full index once.
        try:
            run_index(watch=True)
        except TypeError:
            run_index()
    else:
        run_index()
    return 0


def cmd_pagerank(args: argparse.Namespace) -> int:
    load_dotenv()
    if update_pagerank is None or top_files_and_symbols is None:
        print("PageRank utilities are not available in this environment.", file=sys.stderr)
        return 2
    update_pagerank()
    files, symbols = top_files_and_symbols(topn=args.topn)
    print("\nTop files by PageRank:")
    for i, (f, score) in enumerate(files, 1):
        print(f"{i:>2}. {f} — {score:.5f}")
    print("\nTop symbols by PageRank:")
    for i, (s, score) in enumerate(symbols, 1):
        print(f"{i:>2}. {s} — {score:.5f}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "query":
        return cmd_query(args)
    elif args.cmd == "index":
        return cmd_index(args)
    elif args.cmd == "pagerank":
        return cmd_pagerank(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
