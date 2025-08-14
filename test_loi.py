#!/usr/bin/env python3
"""Test script for LOI condensation feature."""

import json
from codeagent.codesitter.condense import condense_symbol_body

# Example code with multiple references
test_code = '''
def calculate_total(items):
    """Calculate the total price of items."""
    total = 0
    for item in items:
        price = item.get('price', 0)
        quantity = item.get('quantity', 1)
        total += price * quantity
    # Apply discount if total > 100
    if total > 100:
        total = apply_discount(total, 0.1)
    # Apply tax
    tax = calculate_tax(total)
    final = total + tax
    return final

def apply_discount(amount, rate):
    """Apply discount to amount."""
    return amount * (1 - rate)

def calculate_tax(amount):
    """Calculate tax on amount."""
    return amount * 0.08
'''

# Simulate references on lines 12 (price), 18 (apply_discount), 20 (calculate_tax)
ref_lines = [12, 18, 20]

# Test condensation for the main function
sline, eline, body = condense_symbol_body(
    code_s=test_code,
    def_start=8,  # 0-based line for "def calculate_total"
    def_end=21,  # 0-based line for "return final"
    ref_lines=ref_lines,
    pad=2,
    max_lines=50,
)

print("LOI Condensation Test")
print("=" * 50)
print(f"Original lines: 9-22 (1-based)")
print(f"Condensed lines: {sline}-{eline}")
print(f"Number of lines in output: {len(body.splitlines())}")
print("\nCondensed body:")
print("-" * 50)
print(body)
print("-" * 50)
print("\nNote the '…' ellipsis between non-contiguous sections!")
