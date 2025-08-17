-- Migration to add is_def column for Aider-style identifier mode
-- This follows Aider's distinction between definitions and references

-- Step 1: Add is_def column with default TRUE (since all current chunks are definitions)
ALTER TABLE codeindex__code_chunks
ADD COLUMN IF NOT EXISTS is_def BOOLEAN DEFAULT TRUE;

-- Step 2: Backfill existing rows (all current chunks are from defs)
UPDATE codeindex__code_chunks
SET is_def = TRUE
WHERE is_def IS NULL;

-- Step 3: Make column NOT NULL after backfill
ALTER TABLE codeindex__code_chunks
ALTER COLUMN is_def SET NOT NULL;

-- Step 4: Create index for efficient filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_is_def
ON codeindex__code_chunks(is_def)
WHERE is_def = TRUE;

-- Step 5: Create composite index for identifier mode queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_def_name
ON codeindex__code_chunks(is_def, name)
WHERE is_def = TRUE;

-- Verification queries:
-- SELECT is_def, COUNT(*) FROM codeindex__code_chunks GROUP BY is_def;
-- SELECT file, name, symbol_kind, is_def FROM codeindex__code_chunks WHERE name ILIKE '%getDynamicInstance%';
