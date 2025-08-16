# Double .row() Fix Summary

## Problem
Got `AttributeError: 'DataScope' object has no attribute 'row'` because we were calling `.row()` twice on the same scope.

## Root Cause
Incorrect nesting:
```python
with data_scope["files"].row() as f:
    with f.row() as file:  # ❌ WRONG - DataScope doesn't have .row()
        file["symbols"] = ...
```

## Solution Applied
Use single `.row()` call on the table slice:
```python
# For-each-row on the files table (one .row() only)
with data_scope["files"].row() as file:
    # Per-row transforms live as fields on the row Struct to keep KTable V=Struct
    file["symbols"] = file["content"].transform(
        parse_file_to_symbols, filename=file["filename"]
    )
    file["chunks"] = file["symbols"].transform(
        symbols_to_chunks, filename=file["filename"], content=file["content"]
    )
    with file["chunks"].row() as ch:
        # ... rest of processing
```

## Why This Works
1. **Correct API usage**: `.row()` is called once on the table slice (`data_scope["files"]`)
2. **KTable stays valid**: The value remains a Struct with fields (filename, content, symbols, chunks)
3. **Follows CocoIndex pattern**: Matches the official "For-each-row" pattern from docs

## Testing
Run the test:
```bash
./test_final.sh
```

Then run the actual indexing:
```bash
codeagent index --root /Users/mustafaacar/retter/shortlink \
  --map-tokens 1000 --loi-pre 2 --loi-post 12 --loi-hilite
```

## Key Takeaways
- Only call `.row()` once per table slice
- Add fields directly to the row scope
- Nested processing (like `file["chunks"].row()`) is fine for nested collections
