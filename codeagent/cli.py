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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["index", "query", "watch", "pagerank", "repomap"])
    p.add_argument("--root", default=".")
    p.add_argument("--q", help="query text")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--lang", default=None)
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
    args = p.parse_args()

    os.environ.setdefault("CODEAGENT_ROOT", args.root)
    load_dotenv()

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


if __name__ == "__main__":
    main()
