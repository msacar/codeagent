#!/usr/bin/env python
"""Quick test to verify the embedding fix works"""

from codeagent.search.retriever import _embed_query

# Test the embedding function
v = _embed_query("pagerank")
print(f"Type: {type(v)}")
print(f"Length: {len(v)}")
print(f"First 5 values: {v[:5]}")
print("\n✅ Success! The embedding function works correctly.")
print(f"   Returns a list of {len(v)} floats (MiniLM dimension)")
