#!/usr/bin/env python3
"""Test script to verify pgvector type-binding fix"""
import os
import sys
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
import numpy as np

# Load environment
load_dotenv()


def test_pgvector_binding():
    """Test that pgvector binding works correctly with ::vector cast"""

    db_url = os.environ.get("COCOINDEX_DATABASE_URL")
    if not db_url:
        print("❌ COCOINDEX_DATABASE_URL not set in environment")
        return False

    print(f"🔌 Connecting to database...")

    try:
        # Test with connection pool configuration
        def _configure(conn):
            register_vector(conn)

        with ConnectionPool(db_url, configure=_configure) as pool:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Test 1: Check vector extension
                    cur.execute(
                        "SELECT extname FROM pg_extension WHERE extname = 'vector';"
                    )
                    result = cur.fetchone()
                    if not result:
                        print("❌ pgvector extension not installed")
                        return False
                    print("✅ pgvector extension found")

                    # Test 2: Create test vector
                    test_vec = np.random.rand(384).astype(np.float32).tolist()

                    # Test 3: Try using vector with cast (should work)
                    try:
                        cur.execute("SELECT %s::vector AS test_vector", (test_vec,))
                        result = cur.fetchone()
                        print("✅ Vector casting works with ::vector")
                    except Exception as e:
                        print(f"❌ Vector casting failed: {e}")
                        return False

                    # Test 4: Check if code_chunks table exists
                    cur.execute(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = 'code_chunks'
                        AND column_name = 'embedding';
                    """
                    )
                    result = cur.fetchone()
                    if result:
                        print(f"✅ code_chunks.embedding column found: {result[1]}")

                        # Test 5: Try a real query with vector distance
                        cur.execute(
                            """
                            SELECT COUNT(*) FROM code_chunks
                            WHERE embedding IS NOT NULL
                        """
                        )
                        count = cur.fetchone()[0]
                        print(f"📊 Found {count} rows with embeddings")

                        if count > 0:
                            # Test actual vector search
                            cur.execute(
                                """
                                SELECT id, 1.0 - (embedding <=> %s::vector) AS score
                                FROM code_chunks
                                WHERE embedding IS NOT NULL
                                ORDER BY embedding <=> %s::vector
                                LIMIT 1
                            """,
                                (test_vec, test_vec),
                            )
                            result = cur.fetchone()
                            if result:
                                print(
                                    f"✅ Vector search works! Top result: id={result[0]}, score={result[1]:.4f}"
                                )
                    else:
                        print(
                            "⚠️  code_chunks table not found (run 'codeagent index' first)"
                        )

        print("\n🎉 All pgvector tests passed!")
        return True

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pgvector_binding()
    sys.exit(0 if success else 1)
