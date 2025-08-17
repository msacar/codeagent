#!/usr/bin/env python3
"""Test script for capture-first parser changes."""

from codeagent.codesitter.parser import parse_defs_and_refs_from_text

# Test TypeScript with classes and methods
ts_code = """
class UserService {
    constructor(private db: Database) {}

    async getUser(id: string): Promise<User> {
        return await this.db.find(id);
    }

    updateUser(id: string, data: Partial<User>): void {
        this.db.update(id, data);
    }
}

function processData(input: string): string {
    return input.toUpperCase();
}
"""

# Test Python with classes and methods
py_code = """
class DataProcessor:
    def __init__(self, config):
        self.config = config

    def process(self, data):
        return data * 2

    @staticmethod
    def validate(data):
        return len(data) > 0

def standalone_function():
    return "hello"
"""

# Test JavaScript
js_code = """
class Calculator {
    constructor() {
        this.result = 0;
    }

    add(a, b) {
        return a + b;
    }

    multiply(a, b) {
        return a * b;
    }
}

const helper = function(x) {
    return x * 2;
};

function regularFunction() {
    return true;
}
"""

print("Testing capture-first parser...")
print("=" * 50)

# Test TypeScript
print("\n📝 TypeScript parsing:")
defs, refs = parse_defs_and_refs_from_text("test.ts", "test.ts", ts_code)
for d in defs:
    container_info = f" in {d.container}" if d.container else ""
    print(f"  - {d.symbol_kind}: {d.name}{container_info} (L{d.start_line + 1})")
    if d.symbol_kind == "method" and d.name == "constructor":
        print("    ⚠️  Constructor should be normalized to 'constructor' kind")

# Test Python
print("\n🐍 Python parsing:")
defs, refs = parse_defs_and_refs_from_text("test.py", "test.py", py_code)
for d in defs:
    container_info = f" in {d.container}" if d.container else ""
    print(f"  - {d.symbol_kind}: {d.name}{container_info} (L{d.start_line + 1})")

# Test JavaScript
print("\n🟨 JavaScript parsing:")
defs, refs = parse_defs_and_refs_from_text("test.js", "test.js", js_code)
for d in defs:
    container_info = f" in {d.container}" if d.container else ""
    print(f"  - {d.symbol_kind}: {d.name}{container_info} (L{d.start_line + 1})")

print("\n✅ Capture-first parsing test complete!")
print("\nKey improvements:")
print("  • Symbol kinds derived from capture tags (not node types)")
print("  • Container discovery based on captures (not AST node types)")
print("  • Constructor special case handling")
print("  • No per-language tables needed!")
