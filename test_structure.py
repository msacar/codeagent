#!/usr/bin/env python
"""Test script to verify codeagent module structure"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing codeagent module structure...")
print(f"Python path: {sys.path[0]}")

try:
    # Test direct imports from root
    import pipeline.flow
    print("✓ Can import pipeline.flow from root")
except ImportError as e:
    print(f"✗ Cannot import pipeline.flow from root: {e}")

try:
    import search.retriever
    print("✓ Can import search.retriever from root")
except ImportError as e:
    print(f"✗ Cannot import search.retriever from root: {e}")

try:
    import codesitter.parser
    print("✓ Can import codesitter.parser from root")
except ImportError as e:
    print(f"✗ Cannot import codesitter.parser from root: {e}")

try:
    # Test as package
    from codeagent import cli
    print("✓ Can import codeagent.cli")
except ImportError as e:
    print(f"✗ Cannot import codeagent.cli: {e}")

print("\nTo fix the structure, run:")
print("cd /Users/mustafaacar/codeagent")
print("mv codesitter pipeline search queries codeagent/")
print("rm __init__.py  # remove duplicate at root")
print("pip install -e .")
