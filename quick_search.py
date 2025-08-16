#!/usr/bin/env python3
"""Quick vector search for codeagent database."""

import sys
from codeagent.search.retriever import search
from psycopg_pool import ConnectionPool
import os

DATABASE_URL = os.getenv(
    "COCOINDEX_DATABASE_URL", "postgresql://cocoindex:cocoindex@localhost/cocoindex"
)


def main():
    if len(sys.argv) < 2:
        print("Usage: ./quick_search.py <query> [lang] [top_k]")
        print("Examples:")
        print('  ./quick_search.py "PageRank algorithm"')
        print('  ./quick_search.py "parse symbols" python 5')
        sys.exit(1)

    query = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else None
    top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    print(f"Searching for: '{query}'")
    if lang:
        print(f"Language filter: {lang}")
    print(f"Top {top_k} results\n")
    print("=" * 80)

    pool = ConnectionPool(DATABASE_URL)
    results = search(pool, query, top_k=top_k, lang=lang)

    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['name'] or 'unnamed'}")
        print(f"   File: {r['file']}")
        print(f"   Type: {r['symbol_kind'] or 'unknown'}")
        print(f"   Score: {r['score']:.4f}")
        print(f"   Rank: {r['rank']:.6f}" if r["rank"] else "   Rank: N/A")
        if r["header"]:
            print(f"   Header: {r['header'][:100]}...")

    pool.close()


if __name__ == "__main__":
    main()
