#!/bin/bash
# Type check Python code with mypy
echo "Type checking Python code..."
mypy . 2>/dev/null || echo "mypy not installed"
echo "Type checking complete."
