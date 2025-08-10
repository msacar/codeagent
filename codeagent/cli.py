from __future__ import annotations
import os, argparse
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from watchfiles import run_process

from .pipeline.flow import run_index
from .search.retriever import search


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["index", "query", "watch"])
    p.add_argument("--root", default=".")
    p.add_argument("--q", help="query text")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--lang", default=None)
    args = p.parse_args()

    os.environ.setdefault("CODEAGENT_ROOT", args.root)
    load_dotenv()

    if args.cmd == "index":
        run_index()
    elif args.cmd == "query":
        pool = ConnectionPool(os.environ["COCOINDEX_DATABASE_URL"])
        rows = search(pool, args.q or "", top_k=args.k, lang=args.lang)
        for r in rows:
            print(f"[{r['score']:.3f}] {r['file']}:{r['start']}-{r['end']}  {r['symbol_kind']} {r['name']}  ({r['lang']})")
            print(" ", r["header"])
            body = r["body"]
            print(" ", (body[:200] + "…") if len(body) > 200 else body)
            print("---")
    elif args.cmd == "watch":
        def _run(): run_index()
        run_process(args.root, target=_run)


if __name__ == "__main__":
    main()
