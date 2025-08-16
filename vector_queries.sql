-- Vector Similarity Search Examples for pgvector
-- Replace the example vector with an actual embedding vector

-- 1. Basic similarity search with a dummy vector
-- For testing, using a 384-dimensional zero vector (MiniLM-L6-v2 produces 384-dim vectors)
SELECT file, name,
       (embedding <=> ARRAY[0.1, 0.2, 0.3, /* ... repeat 381 more times ... */]::vector) AS distance,
       rank
FROM codeindex__code_chunks
ORDER BY embedding <=> ARRAY[0.1, 0.2, 0.3, /* ... repeat 381 more times ... */]::vector
LIMIT 10;

-- 2. Get vector dimension to verify
SELECT vector_dims(embedding) as dimensions
FROM codeindex__code_chunks
LIMIT 1;

-- 3. Search with a properly sized vector (you need to generate this with the embedding model)
-- Example: searching for "PageRank algorithm"
-- You would need to generate the embedding first using Python:
-- from sentence_transformers import SentenceTransformer
-- model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
-- qvec = model.encode(['PageRank algorithm'], normalize_embeddings=True)[0].tolist()
-- Then use that vector here

-- 4. Hybrid search with keyword filtering
SELECT file, name, symbol_kind,
       (embedding <=> $1::vector) AS distance,
       1.0 - (embedding <=> $1::vector) AS similarity,
       rank
FROM codeindex__code_chunks
WHERE name ILIKE '%pagerank%'
   OR file ILIKE '%pagerank%'
ORDER BY embedding <=> $1::vector ASC, rank DESC
LIMIT 10;

-- 5. Language-specific search
SELECT file, name, symbol_kind,
       (embedding <=> $1::vector) AS distance,
       rank
FROM codeindex__code_chunks
WHERE lang = 'python'
ORDER BY embedding <=> $1::vector ASC, rank DESC
LIMIT 10;

-- 6. Get top-ranked symbols (by PageRank)
SELECT file, name, symbol_kind, rank
FROM codeindex__code_chunks
WHERE rank IS NOT NULL
ORDER BY rank DESC
LIMIT 20;

-- 7. Search within specific symbol types
SELECT file, name, container,
       (embedding <=> $1::vector) AS distance,
       rank
FROM codeindex__code_chunks
WHERE symbol_kind IN ('class', 'function', 'method')
ORDER BY embedding <=> $1::vector ASC, rank DESC
LIMIT 10;

-- 8. Count indexed symbols by type
SELECT symbol_kind, COUNT(*) as count
FROM codeindex__code_chunks
GROUP BY symbol_kind
ORDER BY count DESC;

-- 9. Files with most symbols
SELECT file, COUNT(*) as symbol_count, AVG(rank) as avg_rank
FROM codeindex__code_chunks
GROUP BY file
ORDER BY symbol_count DESC
LIMIT 10;

-- 10. Test vector operations are working
SELECT
    '[1,2,3]'::vector <=> '[3,2,1]'::vector as cosine_distance,
    '[1,2,3]'::vector <-> '[3,2,1]'::vector as l2_distance;
