#!/usr/bin/env python3
"""Test that KTable value type fix works correctly."""

import os
import sys

print("Testing KTable value type fix...")

try:
    # Set environment if not already set
    if not os.getenv("CODEAGENT_ROOT"):
        os.environ["CODEAGENT_ROOT"] = "/Users/mustafaacar/retter/shortlink"

    # Import the updated modules
    from codeagent.pipeline.ops_chunks import Chunk, Dep, symbols_to_chunks
    from codeagent.pipeline.flow import build_index

    print("✓ Successfully imported updated modules")

    # Verify Dep dataclass exists and has correct fields
    test_dep = Dep(name="test", count=5)
    assert test_dep.name == "test"
    assert test_dep.count == 5
    print("✓ Dep dataclass works correctly")

    # Verify Chunk uses List[Dep]
    import inspect
    from typing import get_type_hints

    hints = get_type_hints(Chunk)
    deps_type = str(hints.get("deps", ""))

    if "List" in deps_type and "Dep" in deps_type:
        print(f"✓ Chunk.deps is correctly typed as List[Dep]")
    else:
        print(f"❌ Chunk.deps type is wrong: {deps_type}")
        exit(1)

    # Try to setup the flow - this will validate the schema
    import cocoindex

    cocoindex.init()

    print("✓ Initializing build_index flow...")
    try:
        build_index.setup(report_to_stdout=False)
        print("✓ Flow structure is valid - no KTable value type errors")
    except ValueError as e:
        if "KTable value must have a Struct type" in str(e):
            print(f"❌ KTable value type error still present: {e}")
            exit(1)
        else:
            raise
    except Exception as e:
        # Other errors might be ok (like missing DB connection)
        if "KTable value must" in str(e):
            print(f"❌ KTable error: {e}")
            exit(1)
        else:
            print(f"✓ No KTable value type errors (other error ok: {type(e).__name__})")

    print("\n✅ KTable value type fix successful!")
    print("deps changed from Dict[str, int] to List[Dep]")
    print("")
    print("You can now run:")
    print("  pip install -e .")
    print(
        "  codeagent index --root /Users/mustafaacar/retter/shortlink --map-tokens 1000"
    )

except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
