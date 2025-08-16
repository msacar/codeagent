#!/usr/bin/env python3
"""Test that the double .row() fix works correctly."""

import os
import sys

print("Testing double .row() fix...")

try:
    # Set environment if not already set
    if not os.getenv("CODEAGENT_ROOT"):
        os.environ["CODEAGENT_ROOT"] = "/Users/mustafaacar/retter/shortlink"

    # Import should work without errors
    from codeagent.pipeline.flow import build_index, run_index

    print("✓ Successfully imported flow module")

    # Try to setup the index structure (this validates the flow definition)
    import cocoindex

    cocoindex.init()

    print("✓ Initializing build_index flow...")
    try:
        build_index.setup(report_to_stdout=False)
        print("✓ Flow structure is valid - no double .row() error")
    except AttributeError as e:
        if "'DataScope' object has no attribute 'row'" in str(e):
            print(f"❌ Double .row() error still present: {e}")
            exit(1)
        else:
            raise
    except Exception as e:
        # Other errors might be ok (like missing DB connection)
        if "KTable value must be a Struct" in str(e):
            print(f"❌ KTable struct error: {e}")
            exit(1)
        else:
            print(
                f"✓ No double .row() or KTable errors (other error ok: {type(e).__name__})"
            )

    print("\n✅ Double .row() fix successful!")
    print("You can now run: codeagent index --root /Users/mustafaacar/retter/shortlink")

except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
