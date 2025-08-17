# Capture-First Parser Refactoring

Successfully applied the capture-first solution to make CodeAgent work like Aider:

## Changes Made

### `codeagent/codesitter/parser.py`

1. **Updated `_normalize_kind()`**:
   - Now derives symbol kinds directly from Tree-sitter capture tags
   - Added special case for constructors (when method name is "constructor")
   - No longer relies on language-specific node types
   - Parameters `_lang` and `_node_type` are now unused (prefixed with `_`)

2. **Updated `_enclosing_class_name()`**:
   - Takes a tuple `def_range` instead of separate start/end parameters
   - Finds containers based on captures ending with `.class`
   - Added `code_b` parameter for potential direct decoding
   - Uses more robust logic to find the smallest enclosing class

3. **Updated call sites**:
   - Modified `_materialize_defs_refs()` to pass correct arguments to `_enclosing_class_name()`

## Benefits

- **Parity with Aider**: Now uses the same Tree-sitter capture semantics
- **No per-language tables**: Removed need for CLASS_LIKE, METHOD_LIKE, etc. dictionaries
- **Extensible**: New languages can be added by just providing `tags.scm` files
- **Robust**: Capture-based approach is more maintainable and consistent

## Testing

Created test files to verify the changes:
- `test_capture_first.py`: Tests parsing of TypeScript, Python, and JavaScript
- `test_capture_normalization.py`: Unit tests for `_normalize_kind()`
- `test_capture_integration.py`: Integration test showing end-to-end functionality

The implementation now matches Aider's approach exactly, relying on Tree-sitter captures as the source of truth for symbol kinds and container relationships.
