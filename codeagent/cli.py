from __future__ import annotations
import os
import argparse
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from watchfiles import run_process

from .pipeline.flow import run_index
from .search.retriever import search
from .pipeline.batch_pagerank import BatchPageRankProcessor
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
        "--map-tokens",
        type=int,
        default=1000,
        help="Approx token budget for context rendering (default: 1000)",
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
        pool = ConnectionPool(os.environ["COCOINDEX_DATABASE_URL"])
        rows = search(pool, args.q or "", top_k=args.k, lang=args.lang)
        for r in rows:
            print(
                f"[{r['score']:.3f}] {r['file']}:{r['start']}-{r['end']}  {r['symbol_kind']} {r['name']}  ({r['lang']})"
            )
            print(" ", r["header"])
            body = r["body"]
            print(" ", (body[:200] + "…") if len(body) > 200 else body)
            print("---")
    elif args.cmd == "watch":

        def _run():
            run_index()

        run_process(args.root, target=_run)
    elif args.cmd == "pagerank":
        # Compute and display PageRank results
        processor = BatchPageRankProcessor(args.root)

        if args.load_ranks:
            processor.load_ranks(args.load_ranks)
            print(f"Loaded ranks from {args.load_ranks}")
        else:
            print("Computing PageRank for repository...")
            processor.process_directory(
                patterns=args.include, exclude_patterns=args.exclude
            )
            print("PageRank computation complete!")

        # Display top files
        print(f"\n📊 Top {args.top_n} Files by PageRank:")
        print("=" * 60)
        for i, (file, rank) in enumerate(processor.get_top_files(args.top_n), 1):
            print(f"{i:2}. {file:45} [rank: {rank:.6f}]")

        # Display top symbols
        print(f"\n🔍 Top {args.top_n} Symbols by PageRank:")
        print("=" * 60)
        for i, ((file, symbol), rank) in enumerate(
            processor.get_top_symbols(args.top_n), 1
        ):
            print(f"{i:2}. {symbol:30} in {file:30} [rank: {rank:.6f}]")

        # Save ranks if requested
        if args.save_ranks:
            processor.save_ranks(args.save_ranks)
            print(f"\n✅ Saved ranks to {args.save_ranks}")

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
