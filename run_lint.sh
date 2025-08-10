#!/bin/bash
# Lint Python code with ruff or flake8
echo "Linting Python code..."
ruff check . 2>/dev/null || flake8 . 2>/dev/null || echo "No linter installed (ruff or flake8)"
echo "Linting complete."
