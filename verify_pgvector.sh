#!/bin/bash
set -e

echo "🔍 Checking pgvector setup..."

# Check if the vector extension is installed
psql "postgresql://cocoindex:cocoindex@localhost/cocoindex" -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';" 2>/dev/null || {
    echo "❌ Could not connect to database. Make sure Docker compose is running:"
    echo "   cd /path/to/docker/compose/directory"
    echo "   docker compose up -d"
    exit 1
}

# Check if vector extension is enabled
echo "📦 Checking if vector extension is enabled..."
psql "postgresql://cocoindex:cocoindex@localhost/cocoindex" -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

# Create the extension if not exists
echo "✅ Ensuring vector extension is created..."
psql "postgresql://cocoindex:cocoindex@localhost/cocoindex" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Verify vector operators are available
echo "🔧 Verifying vector operators..."
psql "postgresql://cocoindex:cocoindex@localhost/cocoindex" -c "SELECT oprname FROM pg_operator WHERE oprname IN ('<=>', '<->', '<#>', '<+>');"

# Check if code_chunks table exists and has proper index
echo "📊 Checking code_chunks table and indexes..."
psql "postgresql://cocoindex:cocoindex@localhost/cocoindex" -c "
    SELECT
        tablename,
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = 'code_chunks'
    AND indexdef LIKE '%vector%'
    ORDER BY indexname;
"

# Create recommended HNSW index if not exists
echo "🚀 Creating optimized HNSW index for cosine distance..."
psql "postgresql://cocoindex:cocoindex@localhost/cocoindex" -c "
    CREATE INDEX IF NOT EXISTS code_chunks_embed_hnsw
    ON code_chunks USING hnsw (embedding vector_cosine_ops);
"

echo "✅ pgvector setup verification complete!"
