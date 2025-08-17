# Line References Implementation

## Overview
Added file line references and improved mini-repomap output format for the `codeagent query` command, following Aider's repo-map concept with configurable display options.

## New Features

### 1. Line Reference Display (`--line-refs`)
Control how line numbers are displayed in the output:
- `range` (default): Shows full line range as `:L190-L207`
- `start`: Shows only start line as `:L190`
- `none`: No line references

### 2. Configurable LOI Marker (`--loi-mark`)
Customize the Lines of Interest marker:
- Default: `"▶ "`
- Can be set to any string or empty string to disable

## Usage Examples

### Default Output (range + ▶ marker)
```bash
codeagent query --root /path/to/repo --q getDynamicInstance --map-tokens 800
```

Output:
```
modules/shortlink-api/src/utils/s3-storage.ts:L190-L207
  method getDynamicInstance
  ▶ async getDynamicInstance(tenantId: string, linkCode: string, dynamicCode: string): Promise<DynamicLinkInstance | null> {
    const key = `${tenantId}/dynamic/${linkCode}/instances/${dynamicCode}.json`
    ...
    return obj as DynamicLinkInstance
  }
```

### Start Line Only
```bash
codeagent query --root /path/to/repo --q getDynamicInstance --map-tokens 800 --line-refs start
```

Output:
```
modules/shortlink-api/src/utils/s3-storage.ts:L190
  method getDynamicInstance
  ▶ async getDynamicInstance(...) { ... }
```

### No Line References
```bash
codeagent query --root /path/to/repo --q getDynamicInstance --map-tokens 800 --line-refs none
```

Output:
```
modules/shortlink-api/src/utils/s3-storage.ts
  method getDynamicInstance
  ▶ async getDynamicInstance(...) { ... }
```

### Custom Marker
```bash
codeagent query --root /path/to/repo --q getDynamicInstance --map-tokens 800 --loi-mark '→ '
```

Output:
```
modules/shortlink-api/src/utils/s3-storage.ts:L190-L207
  method getDynamicInstance
  → async getDynamicInstance(...) { ... }
```

### No Marker
```bash
codeagent query --root /path/to/repo --q getDynamicInstance --map-tokens 800 --loi-mark ''
```

Output:
```
modules/shortlink-api/src/utils/s3-storage.ts:L190-L207
  method getDynamicInstance
  async getDynamicInstance(...) { ... }
```

## Implementation Details

### CLI Arguments
```python
grp.add_argument(
    "--line-refs",
    choices=["none", "start", "range"],
    default="range",
    help="Show file line refs: none | start (Lstart) | range (Lstart-Lend).",
)
grp.add_argument(
    "--loi-mark",
    default="▶ ",
    help="Marker string to prefix highlighted anchor lines (default '▶ ').",
)
```

### Output Formatting
The mini-repomap output now:
1. Shows file path with optional line references
2. Indents symbol kind and name
3. Indents condensed body with optional LOI marker
4. Adds blank lines between symbols for readability

### Deterministic Sorting
Results are sorted by:
1. Score (descending)
2. File path
3. Start line number

This ensures consistent output across runs.

## Environment Variables
Can also be controlled via environment:
- `CODEAGENT_MAP_TOKENS`: Token budget
- `CODEAGENT_LOI_MARK`: LOI marker string

Example:
```bash
CODEAGENT_MAP_TOKENS=800 codeagent query \
  --root /path/to/repo \
  --q 'delete dynamic instance endpoint' \
  --k 5
```

## Alignment with Aider

This implementation follows Aider's repo-map concept:
- Shows "critical lines" within a token budget
- Uses Lines of Interest (LOI) condensation
- Prioritizes important code via PageRank
- Provides concise, readable output for LLMs

The line references addition helps with:
- Precise code location identification
- Editor integration (jump to line)
- Cross-referencing in discussions

## Technical Notes

### Safe SQL Parameter Handling
Uses parameterized queries with `ILIKE %s` and `f"%{tok}%"` parameters to avoid literal `%` in SQL strings, preventing psycopg3 placeholder parsing errors.

### Token Estimation
Estimates tokens as `len(text) // 4` for budget management.

### Condenser Integration
Integrates with the project's condenser (`condense_symbol_body`) when available, with a minimal fallback for basic LOI marking.

## Testing

Run the test script to verify functionality:
```bash
python test_line_refs.py
```

This tests:
- Argument parsing
- Output format variations
- Line reference display modes
- LOI marker customization

## References
- Aider repo-map: https://aider.chat/2023/10/22/repomap.html
- psycopg3 parameters: https://www.psycopg.org/psycopg3/docs/basic/params.html
- argparse choices: https://docs.python.org/3/library/argparse.html
