#!/bin/bash
set -e

echo "🔧 Installing codeagent package..."
cd /Users/mustafaacar/codeagent
pip install -e . > /dev/null 2>&1

echo "✅ Package installed"
echo ""
echo "🧪 Running KTable struct test..."
python test_ktable_fix.py

echo ""
echo "📝 Now you can run the actual indexing:"
echo "  codeagent index --root /Users/mustafaacar/retter/shortlink --map-tokens 1000 --loi-pre 2 --loi-post 12 --loi-hilite"
