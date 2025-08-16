# KTable Struct Fix Summary

## Problem
CocoIndex was throwing an error: "KTable values must be Structs"

The issue occurred because transforms that return non-Struct values (like plain strings) were being assigned directly to KTable fields, violating CocoIndex's type system rules.

## Root Cause
In the original code:
```python
f["symbols"] = f["content"].transform(parse_file_to_symbols, filename=f["filename"])
```

This created a new KTable where the value was a plain `str` (JSON string returned by `parse_file_to_symbols`), not a Struct.

## Solution Applied
Wrapped the transforms inside `with f.row() as file:` to make them fields on the row struct:

```python
with data_scope["files"].row() as f:
    # IMPORTANT: do per-row transforms so the KTable's value remains a Struct.
    with f.row() as file:
        file["symbols"] = file["content"].transform(
            parse_file_to_symbols, filename=file["filename"]
        )
        file["chunks"] = file["symbols"].transform(
            symbols_to_chunks, filename=file["filename"], content=file["content"]
        )
    with f["chunks"].row() as ch:
        # ... rest of the code
```

## Why This Works
- The nested `with f.row() as file:` context ensures transforms add fields to the parent struct
- The KTable value remains a Struct (with fields like filename, content, symbols, chunks)
- This satisfies CocoIndex's type system requirement

## Testing
Run the test script to verify:
```bash
./test_and_run.sh
```

Or test manually:
```bash
pip install -e .
codeagent index --root /Users/mustafaacar/retter/shortlink \
  --map-tokens 1000 --loi-pre 2 --loi-post 12 --loi-hilite
```

## Next Steps
After this fix, you should be able to:
1. Index your repository successfully
2. Run queries with LOI (Lines of Interest) condensation
3. See PageRank-weighted results in retrieval
