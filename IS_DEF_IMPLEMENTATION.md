# is_def Flag Implementation

## Overview
Implemented explicit `is_def` flag to distinguish definitions from references, following Aider's Tree-sitter approach exactly.

## Implementation Details

### 1. Data Model Changes

#### Chunk Dataclass (`pipeline/ops_chunks.py`)
```python
@dataclass(frozen=True)
class Chunk:
    # ... existing fields ...
    is_def: bool  # True for definitions, False for references
```

#### Database Schema
- New column: `is_def BOOLEAN NOT NULL`
- Indexes:
  - `idx_code_chunks_is_def` - For efficient filtering
  - `idx_code_chunks_def_name` - Composite index for identifier queries

### 2. Parser Integration

The parser already distinguishes definitions from references based on Tree-sitter capture names:
- `definition.*` → Definition
- `name.definition.*` → Definition
- `name.reference.*` → Reference

All chunks created from `defs` array have `is_def=True`.

### 3. Retriever Changes

Identifier mode now uses strict `is_def = TRUE` filter:

```sql
WHERE is_def = TRUE
  AND (name ILIKE %s OR file ILIKE %s)
```

This aligns with Aider's behavior of only including definitions in the repo-map.

## Migration Steps

### 1. Apply Database Migration
```bash
python apply_is_def_migration.py
```

This will:
- Add `is_def` column with default `TRUE`
- Backfill existing rows (all are definitions)
- Create indexes for performance

### 2. Re-index Code
```bash
codeagent index
```

New chunks will have `is_def` properly set.

### 3. Verify Implementation
```bash
python verify_is_def.py
```

## Aider Alignment

This implementation follows Aider's approach exactly:

1. **Tree-sitter Semantics**: Uses capture names (`definition.*` vs `reference.*`) to determine is_def
2. **Definitions Only**: Identifier mode filters to `is_def = TRUE` only
3. **No Embeddings**: Identifier scoring uses PageRank + lexical, no vector similarity
4. **Token Budget**: Output respects `--map-tokens` limit

## Query Behavior

### Identifier Queries
```bash
codeagent query --q getDynamicInstance --map-tokens 800
```
- Uses `is_def = TRUE` filter
- Ranks by PageRank + lexical match
- No embedding similarity in score

### Natural Language Queries
```bash
codeagent query --q "find user authentication" --k 10
```
- Uses embedding-first approach
- Combines vector similarity with PageRank
- No is_def filter

## SQL Verification Queries

```sql
-- Check distribution
SELECT is_def, COUNT(*)
FROM codeindex__code_chunks
GROUP BY is_def;

-- Find specific symbol
SELECT file, name, symbol_kind, is_def
FROM codeindex__code_chunks
WHERE name ILIKE '%getDynamicInstance%';

-- Top files by PageRank (definitions only)
SELECT file, AVG(rank) as avg_rank
FROM codeindex__code_chunks
WHERE is_def = TRUE
GROUP BY file
ORDER BY avg_rank DESC
LIMIT 20;
```

## Rollback (if needed)

```bash
python apply_is_def_migration.py --rollback
```

This will drop the column and indexes.

## References

- Aider's repo-map: Built from "most important classes and functions" (definitions)
- Tree-sitter captures provide `definition.*` vs `reference.*` semantics
- PageRank over dependency graph for importance ranking
- Token budget controls output size

See:
- https://aider.chat/docs/repomap.html
- https://aider.chat/2023/10/22/repomap.html
- https://tree-sitter.github.io/tree-sitter/3-syntax-highlighting.html
