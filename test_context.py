#!/usr/bin/env python
"""
Test the context map feature
"""

import subprocess
import sys


def test_context_command():
    """Test various context command scenarios"""

    print("Testing context command...")

    # Test 1: Basic context with prompt
    print("\n1. Testing basic context with prompt:")
    cmd = [
        sys.executable,
        "-m",
        "codeagent.cli",
        "context",
        "--root",
        ".",
        "--q",
        "pagerank implementation",
        "--map-tokens",
        "500",
        "--top-files",
        "5",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Basic context command works")
            print(f"  Output preview: {result.stdout[:200]}...")
        else:
            print(f"✗ Command failed: {result.stderr}")
    except Exception as e:
        print(f"✗ Error running command: {e}")

    # Test 2: Context with file seed
    print("\n2. Testing context with file seed:")
    cmd = [
        sys.executable,
        "-m",
        "codeagent.cli",
        "context",
        "--root",
        ".",
        "--q",
        "batch processing",
        "--file",
        "codeagent/pipeline/batch_pagerank.py",
        "--map-tokens",
        "800",
        "--top-files",
        "10",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Context with file seed works")
            # Check if the seeded file appears in output
            if "batch_pagerank.py" in result.stdout:
                print("  ✓ Seeded file appears in output")
        else:
            print(f"✗ Command failed: {result.stderr}")
    except Exception as e:
        print(f"✗ Error running command: {e}")

    # Test 3: Context with exclude patterns
    print("\n3. Testing context with exclude patterns:")
    cmd = [
        sys.executable,
        "-m",
        "codeagent.cli",
        "context",
        "--root",
        ".",
        "--q",
        "parser implementation",
        "--exclude",
        "**/__pycache__/**",
        "**/*.egg-info/**",
        "--map-tokens",
        "600",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Context with exclude patterns works")
            # Check that excluded patterns don't appear
            if "__pycache__" not in result.stdout and ".egg-info" not in result.stdout:
                print("  ✓ Excluded patterns not in output")
        else:
            print(f"✗ Command failed: {result.stderr}")
    except Exception as e:
        print(f"✗ Error running command: {e}")

    # Test 4: Error case - no prompt or files
    print("\n4. Testing error handling (no prompt or files):")
    cmd = [sys.executable, "-m", "codeagent.cli", "context", "--root", "."]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("✓ Properly handles missing prompt/files")
            if "Provide --q PROMPT and/or --file FILE" in result.stderr:
                print("  ✓ Shows helpful error message")
        else:
            print("✗ Should have failed without prompt or files")
    except Exception as e:
        print(f"✗ Error running command: {e}")


if __name__ == "__main__":
    test_context_command()
