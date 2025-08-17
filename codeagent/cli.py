from __future__ import annotations
import os
import argparse
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from watchfiles import run_process
from cocoindex import utils as cx_utils

from .pipeline.flow import run_index, build_index
from .search.retriever import search
from .pipeline.pagerank_update import top_files_and_symbols, update_pagerank
from .repomap import RepoMap
from .context import ContextMapBuilder


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "cmd", choices=["index", "query", "watch", "pagerank", "repomap", "context"]
    )
    p.add_argument("--root", default=".")
    p.add_argument("--q", help="query text")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--lang", default=None)

    # Aider-style repo-map / condenser knobs
    grp = p.add_argument_group("repo-map options (Aider-style knobs)")
    grp.add_argument(
        "--map-tokens",
        type=int,
        default=None,
        help="Approx token budget for condensed bodies (similar to Aider's --map-tokens).",
    )
    grp.add_argument(
        "--loi-pre",
        type=int,
        default=None,
        help="Lines of context before each anchor (default 2).",
    )
    grp.add_argument(
        "--loi-post",
        type=int,
        default=None,
        help="Lines of context after each anchor (default 12 for funcs/methods, 6 otherwise).",
    )
    grp.add_argument(
        "--loi-max-lines",
        type=int,
        default=None,
        help="Max lines per condensed body (guardrail if no token budget).",
    )
    grp.add_argument(
        "--loi-hilite",
        action="store_true",
        help="Highlight anchor lines in condensed bodies.",
    )
    grp.add_argument(
        "--loi-mark",
        default=None,
        help="Marker string to prefix highlighted anchor lines (default '▶').",
    )
    p.add_argument(
        "--include", nargs="+", help="Glob patterns to include (e.g. **/*.ts **/*.py)"
    )
    p.add_argument(
        "--exclude",
        nargs="+",
        help="Glob patterns to exclude (e.g. **/*.d.ts **/@types/** **/__tests__/**)",
    )
    p.add_argument("--top-n", type=int, default=10, help="Number of top items to show")
    p.add_argument("--save-ranks", help="Save PageRank results to JSON file")
    p.add_argument("--load-ranks", help="Load PageRank results from JSON file")
    p.add_argument("--focus-files", nargs="+", help="Files to focus on in repo map")
    p.add_argument(
        "--max-tokens", type=int, default=2000, help="Max tokens for repo map"
    )
    # Context-specific arguments
    p.add_argument(
        "--file",
        dest="chat_files",
        action="append",
        default=[],
        help="Seed PageRank with this file (repeatable)",
    )
    p.add_argument(
        "--top-files",
        type=int,
        default=25,
        help="Max files to include before token budget is applied",
    )
    args = p.parse_args()

    os.environ.setdefault("CODEAGENT_ROOT", args.root)
    load_dotenv()

    # Thread condenser settings via env so pipeline ops can read them
    if args.map_tokens is not None:
        os.environ["CODEAGENT_MAP_TOKENS"] = str(args.map_tokens)
    if args.loi_pre is not None:
        os.environ["CODEAGENT_LOI_PRE"] = str(args.loi_pre)
    if args.loi_post is not None:
        os.environ["CODEAGENT_LOI_POST"] = str(args.loi_post)
    if args.loi_max_lines is not None:
        os.environ["CODEAGENT_LOI_MAX_LINES"] = str(args.loi_max_lines)
    if args.loi_hilite:
        os.environ["CODEAGENT_LOI_HILITE"] = "1"
    if args.loi_mark is not None:
        os.environ["CODEAGENT_LOI_MARK"] = args.loi_mark

    if args.cmd == "index":
        run_index()
    elif args.cmd == "query":

        def _configure(conn):  # runs on every new connection from the pool
            register_vector(conn)

        with ConnectionPool(
            os.environ["COCOINDEX_DATABASE_URL"], configure=_configure
        ) as pool:
            rows = search(pool, args.q or "", top_k=args.k, lang=args.lang)
            for r in rows:
                head = f"[{r['score']:.3f}] {r['file']}:{r['start']}-{r['end']}  {r['symbol_kind']} {r['name']}  ({r['lang']})"
                container = r.get("container") or ""
                if container:
                    print(head)
                    print(f"  container → {container}")
                else:
                    print(head)
                print(" ", r["header"])
                body = r["body"]
                print(" ", (body[:200] + "…") if len(body) > 200 else body)
                print("---")
    elif args.cmd == "watch":

        def _run():
            run_index()

        run_process(args.root, target=_run)
    elif args.cmd == "pagerank":

        def _configure(conn):  # runs on every new connection from the pool
            register_vector(conn)

        with ConnectionPool(
            os.environ["COCOINDEX_DATABASE_URL"], configure=_configure
        ) as pool:
            # ensure the table ranks are fresh
            table = cx_utils.get_target_default_name(build_index, "code_chunks")
            try:
                touched = update_pagerank(pool, table)
                if touched:
                    print(f"(re)computed PageRank (updated {touched} rows)")
            except Exception:
                pass
            files, syms = top_files_and_symbols(pool, table, top_n=args.top_n)
            print("\n📊 Top Files by PageRank:")
            print("============================================================")
            width = max((len(f) for f, _ in files), default=0)
            for i, (f, r) in enumerate(files, 1):
                print(f"{i:2d}. {f:<{width}}  [rank: {r:.6f}]")
            print("\n🔍 Top Symbols (weighted by citing file PR):")
            print("============================================================")
            w2 = max((len(n) for n, _, _ in syms), default=0)
            for i, (name, def_file, score) in enumerate(syms, 1):
                print(f"{i:2d}. {name:<{w2}}  in {def_file}  [score: {score:.6f}]")

    elif args.cmd == "repomap":
        # Generate and display repository map
        repo_map = RepoMap(
            args.root,
            max_tokens=args.max_tokens,
            include=args.include,
            exclude=args.exclude,
        )
        print("Generating repository map...")

        map_content = repo_map.generate(focus_files=args.focus_files)
        print(map_content)

        # Show statistics
        lines = map_content.split("\n")
        tokens = sum(len(line.split()) for line in lines)
        print("\n📈 Map Statistics:")
        print(f"  Lines: {len(lines)}")
        print(f"  Approx tokens: {tokens}")

    elif args.cmd == "context":
        # Build chat-aware context map using personalized PageRank
        import sys

        prompt = args.q or ""
        if not prompt and not args.chat_files:
            print(
                "Provide --q PROMPT and/or --file FILE to seed the context map.",
                file=sys.stderr,
            )
            sys.exit(2)

        builder = ContextMapBuilder(
            args.root, include=args.include, exclude=args.exclude
        )

        print("Building context map...")
        context = builder.build_context_map(
            prompt=prompt,
            chat_files=args.chat_files,
            map_tokens=args.map_tokens,
            top_files=args.top_files,
        )

        # Display the context map
        print(f"\n📌 Context map for: {prompt!r}")
        print("=" * 60)

        for i, item in enumerate(context, 1):
            print(f"{i:2d}. {item['file']:45} [rank: {item['rank']:.6f}]")

            for h in item.get("highlights", []):
                # Compact: header then first line of body
                print(f"    - {h['header']}")
                if h["body"].strip():
                    print(f"      {h['body']}")

            if item.get("highlights"):
                print()

        # Show token usage
        total_chars = sum(
            len(item["file"])
            + sum(len(h["header"]) + len(h["body"]) for h in item.get("highlights", []))
            for item in context
        )
        approx_tokens = total_chars // 4
        print("\n📊 Context Statistics:")
        print(f"  Files included: {len(context)}")
        print(f"  Approx tokens used: {approx_tokens}/{args.map_tokens}")


if __name__ == "__main__":
    main()
