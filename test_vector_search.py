#!/usr/bin/env python3
"""Test vector similarity search in the database."""

import os
import sys
import psycopg
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

# Database connection
DATABASE_URL = os.getenv(
    "COCOINDEX_DATABASE_URL", "postgresql://cocoindex:cocoindex@localhost/cocoindex"
)

# Embedding model (same as used during indexing)
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def embed_query(query_text: str):
    """Generate embedding for a query."""
    model = SentenceTransformer(MODEL_NAME)
    vec = model.encode([query_text], normalize_embeddings=True)[0]
    return vec.tolist()


def search_direct(query_text: str, top_k: int = 10):
    """Direct SQL search with vector similarity."""

    # Generate embedding for the query
    qvec = embed_query(query_text)

    # Connect to database
    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            # Basic vector similarity search
            sql = """
            SELECT
                file,
                name,
                symbol_kind,
                container,
                (embedding <=> %s::vector) AS distance,
                rank,
                1.0 - (embedding <=> %s::vector) AS similarity_score
            FROM codeindex__code_chunks
            ORDER BY embedding <=> %s::vector ASC, rank DESC
            LIMIT %s
            """

            cur.execute(sql, (qvec, qvec, qvec, top_k))
            results = cur.fetchall()

            print(f"\n🔍 Search results for: '{query_text}'")
            print("=" * 80)

            for i, row in enumerate(results, 1):
                file, name, kind, container, dist, rank, score = row
                print(f"\n{i}. {name or 'unnamed'}")
                print(f"   File: {file}")
                print(f"   Type: {kind or 'unknown'}")
                print(f"   Container: {container or 'none'}")
                print(f"   Distance: {dist:.4f}")
                print(f"   Similarity: {score:.4f}")
                print(f"   PageRank: {rank:.6f}" if rank else "   PageRank: N/A")


def search_with_filters(query_text: str, lang: str = None, top_k: int = 10):
    """Search with additional filters."""

    qvec = embed_query(query_text)

    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            # Build WHERE clause
            where_clauses = []
            params = []

            if lang:
                where_clauses.append("lang = %s")
                params.append(lang)

            # Add keyword filter for better hybrid search
            keywords = query_text.split()
            if keywords:
                keyword = keywords[0]
                if len(keyword) >= 3:
                    where_clauses.append("(name ILIKE %s OR file ILIKE %s)")
                    params.extend([f"%{keyword}%", f"%{keyword}%"])

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Add vector params at the end
            params.extend([qvec, qvec, qvec, top_k])

            sql = f"""
            SELECT
                file,
                name,
                symbol_kind,
                lang,
                header,
                (embedding <=> %s::vector) AS distance,
                rank
            FROM codeindex__code_chunks
            {where_sql}
            ORDER BY embedding <=> %s::vector ASC, rank DESC
            LIMIT %s
            """

            cur.execute(sql, params)
            results = cur.fetchall()

            print(
                f"\n🔍 Filtered search for: '{query_text}'"
                + (f" (lang={lang})" if lang else "")
            )
            print("=" * 80)

            for i, row in enumerate(results, 1):
                file, name, kind, language, header, dist, rank = row
                print(f"\n{i}. {name or 'unnamed'} [{language}]")
                print(f"   File: {file}")
                print(f"   Type: {kind or 'unknown'}")
                print(f"   Distance: {dist:.4f}")
                print(f"   PageRank: {rank:.6f}" if rank else "   PageRank: N/A")
                if header:
                    print(f"   Preview: {header[:100]}...")


def test_db_connection():
    """Test if we can connect and see the table structure."""

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute(
                """
                SELECT COUNT(*)
                FROM codeindex__code_chunks
            """
            )
            count = cur.fetchone()[0]
            print(f"✅ Database connected. Found {count} code chunks indexed.")

            # Show sample data
            cur.execute(
                """
                SELECT file, name, lang, symbol_kind
                FROM codeindex__code_chunks
                LIMIT 5
            """
            )

            print("\nSample indexed symbols:")
            for row in cur.fetchall():
                print(f"  - {row[1]} ({row[3]}) in {row[0]} [{row[2]}]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test vector search in code chunks")
    parser.add_argument("query", nargs="?", help="Search query text")
    parser.add_argument("--lang", help="Filter by language (e.g., python, typescript)")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--test", action="store_true", help="Test database connection")

    args = parser.parse_args()

    if args.test:
        test_db_connection()
    elif args.query:
        print("Loading embedding model...")
        if args.lang:
            search_with_filters(args.query, lang=args.lang, top_k=args.top_k)
        else:
            search_direct(args.query, top_k=args.top_k)
    else:
        # Run some example searches
        print("Running example searches...\n")
        test_db_connection()
        print("\n" + "=" * 80)

        # Example queries
        examples = [
            "parse tree-sitter symbols",
            "embedding vector database",
            "PageRank algorithm",
        ]

        for example in examples:
            search_direct(example, top_k=5)
