#!/bin/bash
# Format Python code with black and isort
echo "Formatting Python code..."
black . --quiet 2>/dev/null || echo "black not installed"
isort . --quiet 2>/dev/null || echo "isort not installed"
echo "Formatting complete."
