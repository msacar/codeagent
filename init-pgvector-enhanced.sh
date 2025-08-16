#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create vector extension
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Note: The HNSW index will be created later when the code_chunks table exists
    -- The application or migration scripts should handle index creation
EOSQL

echo "✅ pgvector extension initialized successfully"
