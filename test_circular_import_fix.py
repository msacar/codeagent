#!/usr/bin/env python3
"""Test that circular import is fixed."""

print("Testing circular import fix...")

try:
    # This should not raise ImportError anymore
    from codeagent.pipeline.flow import run_index, build_index

    print("✓ Successfully imported from flow.py")

    from codeagent.pipeline.pagerank_update import (
        update_pagerank,
        top_files_and_symbols,
    )

    print("✓ Successfully imported from pagerank_update.py")

    # Test that functions have correct signatures
    import inspect

    # Check update_pagerank signature
    sig = inspect.signature(update_pagerank)
    params = list(sig.parameters.keys())
    assert "pool" in params, "update_pagerank should have 'pool' parameter"
    assert "table" in params, "update_pagerank should have 'table' parameter"
    print(f"✓ update_pagerank has correct signature: {params}")

    # Check top_files_and_symbols signature
    sig = inspect.signature(top_files_and_symbols)
    params = list(sig.parameters.keys())
    assert "pool" in params, "top_files_and_symbols should have 'pool' parameter"
    assert "table" in params, "top_files_and_symbols should have 'table' parameter"
    assert "top_n" in params, "top_files_and_symbols should have 'top_n' parameter"
    print(f"✓ top_files_and_symbols has correct signature: {params}")

    print("\n✅ All tests passed! Circular import is fixed.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Circular import is NOT fixed")
    exit(1)
except AssertionError as e:
    print(f"❌ Assertion error: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    exit(1)
