#!/usr/bin/env python3
"""
Apply is_def column migration for Aider-style identifier mode.
This adds the is_def column to distinguish definitions from references.
"""

import os
import sys
import psycopg
from dotenv import load_dotenv
import cocoindex
from cocoindex import utils as cx_utils
from codeagent.pipeline.flow import build_index


def apply_migration():
    """Apply the is_def column migration."""
    load_dotenv()

    db_url = os.environ.get("COCOINDEX_DATABASE_URL")
    if not db_url:
        print("ERROR: COCOINDEX_DATABASE_URL not set")
        return False

    # Get the actual table name
    table = cx_utils.get_target_default_name(build_index, "code_chunks")
    print(f"Applying migration to table: {table}")

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Check if column already exists
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = %s AND column_name = 'is_def'
                """,
                    (table,),
                )

                if cur.fetchone():
                    print("✓ Column is_def already exists")
                    return True

                print("Adding is_def column...")

                # Step 1: Add column with default
                cur.execute(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN is_def BOOLEAN DEFAULT TRUE
                """
                )
                print("✓ Added is_def column")

                # Step 2: Backfill (redundant but explicit)
                cur.execute(
                    f"""
                    UPDATE {table}
                    SET is_def = TRUE
                    WHERE is_def IS NULL
                """
                )
                rows_updated = cur.rowcount
                print(f"✓ Backfilled {rows_updated} rows")

                # Step 3: Make NOT NULL
                cur.execute(
                    f"""
                    ALTER TABLE {table}
                    ALTER COLUMN is_def SET NOT NULL
                """
                )
                print("✓ Made is_def NOT NULL")

                # Step 4: Create indexes
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_is_def
                    ON {table}(is_def)
                    WHERE is_def = TRUE
                """
                )
                print("✓ Created is_def index")

                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_def_name
                    ON {table}(is_def, name)
                    WHERE is_def = TRUE
                """
                )
                print("✓ Created composite index")

                # Verify
                cur.execute(
                    f"""
                    SELECT is_def, COUNT(*)
                    FROM {table}
                    GROUP BY is_def
                """
                )
                results = cur.fetchall()
                print("\nVerification:")
                for is_def, count in results:
                    print(f"  is_def={is_def}: {count} rows")

                conn.commit()
                print("\n✅ Migration completed successfully!")
                return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


def rollback_migration():
    """Rollback the is_def column migration if needed."""
    load_dotenv()

    db_url = os.environ.get("COCOINDEX_DATABASE_URL")
    if not db_url:
        print("ERROR: COCOINDEX_DATABASE_URL not set")
        return False

    table = cx_utils.get_target_default_name(build_index, "code_chunks")

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Drop indexes
                cur.execute(f"DROP INDEX IF EXISTS idx_{table}_is_def")
                cur.execute(f"DROP INDEX IF EXISTS idx_{table}_def_name")

                # Drop column
                cur.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS is_def")

                conn.commit()
                print("✅ Rollback completed")
                return True

    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage is_def column migration")
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback the migration"
    )
    args = parser.parse_args()

    if args.rollback:
        success = rollback_migration()
    else:
        success = apply_migration()

    sys.exit(0 if success else 1)
