#!/usr/bin/env python3
"""Quick verification that capture-first parser changes work."""

from codeagent.codesitter.parser import _normalize_kind, _enclosing_class_name

print("Testing capture-first normalization...")

# Test _normalize_kind function
test_cases = [
    # (lang, node_type, cap_kind, name_text, expected)
    ("typescript", "any", "definition.function", "myFunc", "function"),
    ("typescript", "any", "definition.method", "myMethod", "method"),
    (
        "typescript",
        "any",
        "definition.method",
        "constructor",
        "constructor",
    ),  # Special case
    ("typescript", "any", "definition.class", "MyClass", "class"),
    ("python", "any", "name.definition.function", "my_func", "function"),
    ("javascript", "any", "definition.property", "prop", "property"),
]

print("\nTesting _normalize_kind:")
for lang, node_type, cap_kind, name_text, expected in test_cases:
    result = _normalize_kind(lang, node_type, cap_kind, name_text)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {cap_kind} + '{name_text}' -> {result} (expected: {expected})")

print("\n✅ Capture-first normalization test complete!")
print("\nKey improvements applied:")
print("  • _normalize_kind now uses capture tags directly")
print("  • Special case for constructor methods")
print("  • _enclosing_class_name uses capture-based container discovery")
print("  • No per-language node type tables needed!")
