#!/usr/bin/env python
"""Quick test to verify TypeScript query is loaded properly."""

from codeagent.codesitter.tags_loader import load_query_text
from grep_ast.tsl import get_language

# Test 1: Query loading
for lang in ["typescript", "javascript", "python"]:
    q = load_query_text(lang)
    print(f"{lang} query loaded? {bool(q)}, len={0 if not q else len(q)}")

# Test 2: Language availability
for lang in ["typescript", "javascript", "python"]:
    try:
        l = get_language(lang)
        print(f"{lang} language ok: {l is not None}")
    except Exception as e:
        print(f"{lang} language error: {e}")

print("\nIf all show True and non-zero lengths, queries are properly loaded!")
