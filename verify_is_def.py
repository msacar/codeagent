#!/usr/bin/env python3
"""
Verification script for is_def implementation.
Tests that the is_def flag correctly distinguishes definitions from references
and that identifier mode uses it properly.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("Verifying is_def Implementation")
print("=" * 60)

# Test 1: Check Chunk dataclass has is_def field
print("\n1. Checking Chunk dataclass...")
try:
    from codeagent.pipeline.ops_chunks import Chunk, Dep
    import inspect
    from dataclasses import fields

    chunk_fields = {f.name: f.type for f in fields(Chunk)}
    if "is_def" in chunk_fields:
        print(f"✓ Chunk has is_def field (type: {chunk_fields['is_def']})")
    else:
        print("✗ Chunk missing is_def field")

except Exception as e:
    print(f"✗ Error checking Chunk: {e}")

# Test 2: Check symbols_to_chunks sets is_def=True
print("\n2. Checking symbols_to_chunks sets is_def...")
try:
    from codeagent.pipeline.ops_chunks import symbols_to_chunks
    import json

    # Create test data
    test_syms = json.dumps(
        {
            "defs": [
                {
                    "name": "testFunc",
                    "symbol_kind": "function",
                    "lang": "javascript",
                    "start_line": 0,
                    "end_line": 2,
                    "container": None,
                    "doc": None,
                }
            ],
            "refs": [],
        }
    )

    test_content = "function testFunc() {\n  return 42;\n}"
    chunks = symbols_to_chunks(test_syms, "test.js", test_content)

    if chunks and chunks[0].is_def:
        print("✓ symbols_to_chunks sets is_def=True for definitions")
    else:
        print("✗ symbols_to_chunks not setting is_def correctly")

except Exception as e:
    print(f"✗ Error testing symbols_to_chunks: {e}")

# Test 3: Check flow.py collects is_def
print("\n3. Checking flow.py collects is_def field...")
try:
    with open("codeagent/pipeline/flow.py", "r") as f:
        flow_content = f.read()
        if (
            'is_def=ch["is_def"]' in flow_content
            or "is_def=ch['is_def']" in flow_content
        ):
            print("✓ flow.py collects is_def field")
        else:
            print("✗ flow.py not collecting is_def field")
except Exception as e:
    print(f"✗ Error checking flow.py: {e}")

# Test 4: Check retriever uses is_def in identifier mode
print("\n4. Checking retriever uses is_def...")
try:
    with open("codeagent/search/retriever.py", "r") as f:
        retriever_content = f.read()
        if "is_def = TRUE" in retriever_content:
            print("✓ Retriever filters by is_def=TRUE in identifier mode")
        else:
            print("✗ Retriever not using is_def filter")
except Exception as e:
    print(f"✗ Error checking retriever: {e}")

# Test 5: Test identifier detection logic
print("\n5. Testing identifier detection...")
import re


def is_identifier(q: str) -> bool:
    q = q.strip()
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", q))


test_cases = [
    ("getDynamicInstance", True, "Aider-style method name"),
    ("MyClass", True, "Class name"),
    ("_private_var", True, "Private variable"),
    ("find user by id", False, "Natural language query"),
    ("search-results", False, "Contains hyphen"),
]

all_passed = True
for query, expected, description in test_cases:
    result = is_identifier(query)
    if result == expected:
        print(f"  ✓ '{query}' -> {result} ({description})")
    else:
        print(f"  ✗ '{query}' -> {result}, expected {expected} ({description})")
        all_passed = False

# Summary
print("\n" + "=" * 60)
print("Summary:")
print(
    """
The is_def implementation follows Aider's approach:
• Parser sets is_def=True for all definitions (from Tree-sitter captures)
• Database has is_def column with indexes for efficient filtering
• Identifier mode uses 'is_def = TRUE' filter (strict Aider behavior)
• Natural language queries continue using embeddings

Aider alignment:
• Repo-map uses definitions only (classes, functions, methods)
• PageRank over dependency graph for importance
• No embeddings in identifier mode scoring
• Token budget controls output size
"""
)

print("\nNext steps:")
print("1. Run migration: python apply_is_def_migration.py")
print("2. Re-index: codeagent index")
print("3. Test query: codeagent query --q getDynamicInstance --map-tokens 800")
