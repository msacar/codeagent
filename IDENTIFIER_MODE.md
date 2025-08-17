# Aider-Style Identifier Mode Implementation

## Summary
Successfully implemented Aider-style identifier mode for code search, providing better ranking for identifier queries by using PageRank + lexical matching without embeddings.

## Key Changes

### 1. Retriever (`codeagent/search/retriever.py`)
- Added identifier detection using regex pattern `[A-Za-z_][A-Za-z0-9_]*`
- Implemented dual search modes:
  - **Identifier mode**: For single identifiers (e.g., `getDynamicInstance`)
    - Uses PageRank + lexical matching only
    - No embedding similarity in scoring
    - **Filters by `is_def = TRUE` (definitions only)**
    - Boosts callable symbols (methods/functions) over types
  - **Natural language mode**: For queries with spaces/non-identifier characters
    - Uses existing embedding-first approach
    - Combines vector similarity with PageRank
- Added safety fallback: if identifier mode returns no results, falls back to vector search
- **Fixed psycopg placeholder parsing**: Using parameterized `ILIKE %s` patterns to avoid literal `%` in SQL

### 2. CLI (`codeagent/cli.py`)
- Enhanced `query` command to support Aider-style output with token budget
- When `--map-tokens` is specified:
  - Groups results by file
  - Shows condensed symbol bodies with `▶` marker
  - Respects token budget limit
  - Uses Lines of Interest (LOI) condensation if available

### 3. Data Model (`codeagent/pipeline/ops_chunks.py`)
- **Added `is_def` field to Chunk dataclass**
- All chunks created from definitions have `is_def=True`
- Enables strict filtering for identifier queries

### 4. Database Schema
- **Added `is_def` column to distinguish definitions from references**
- Created indexes for efficient filtering
- See `IS_DEF_IMPLEMENTATION.md` for migration details

## Usage Examples

### Identifier Query (Aider-style)
```bash
# Search for a specific function/method
codeagent query --root /path/to/repo --q getDynamicInstance --k 5

# With token budget for Aider-style output
CODEAGENT_MAP_TOKENS=800 codeagent query \
  --root /path/to/repo \
  --q getDynamicInstance \
  --map-tokens 800
```

Output format with token budget:
```
modules/shortlink-api/src/utils/s3-storage.ts
  method getDynamicInstance
  ▶ async getDynamicInstance(tenantId: string, linkCode: string, dynamicCode: string): Promise<DynamicLinkInstance | null> {
    const key = `${tenantId}/dynamic/${linkCode}/instances/${dynamicCode}.json`
    ...
    return obj as DynamicLinkInstance
  }
```

### Natural Language Query
```bash
# Natural language queries still use embedding-first approach
codeagent query --root /path/to/repo --q "find user authentication" --k 10
```

## Why This Matters

1. **Better Precision for Identifiers**: When searching for specific symbols (functions, classes, methods), the identifier mode provides more accurate results by focusing on exact/partial name matches and using PageRank importance.

2. **Aider Parity**: Matches Aider's behavior where the repo-map is built using Tree-sitter captures + dependency graph + PageRank, not embedding-first selection.

3. **Flexible Fallback**: The system gracefully handles edge cases by falling back to vector search if identifier mode yields no results.

4. **PostgreSQL Compatibility**: Properly handles psycopg3's placeholder parsing by using parameterized patterns instead of literal `%` in SQL strings.

## Technical Notes

### psycopg Placeholder Fix
The initial implementation had literal `%` characters in the SQL string which psycopg3 interprets as placeholders, causing `ProgrammingError: only '%s', '%b', '%t' are allowed as placeholders`.

Fixed by:
- Using `ILIKE %s` with parameterized patterns (`f"%{tok}%"`)
- Avoids literal `%` in SQL strings
- Follows psycopg3 best practices for parameter passing

## Verification

Run the test script to verify the implementation:
```bash
./run_test.sh
# or
python test_identifier_mode.py
```

The test script verifies:
- Identifier detection logic
- Dual mode behavior explanation
- CLI token budget formatting

## References
- Aider repo-map: Uses captures → dependency graph → PageRank within token budget
- No embedding-first selection for identifier lookups
- See: https://aider.chat/2023/10/22/repomap.html
- psycopg3 documentation on parameter passing
