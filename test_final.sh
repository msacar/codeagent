#!/bin/bash
set -e

echo "🔧 Re-installing codeagent package..."
cd /Users/mustafaacar/codeagent
pip install -e . > /dev/null 2>&1

echo "✅ Package installed"
echo ""
echo "🧪 Running double .row() fix test..."
python test_row_fix.py

echo ""
echo "📝 Ready to run the actual indexing:"
echo "  codeagent index --root /Users/mustafaacar/retter/shortlink --map-tokens 1000 --loi-pre 2 --loi-post 12 --loi-hilite"
echo ""
echo "Then test a query:"
echo "  codeagent query --root /Users/mustafaacar/retter/shortlink --q \"dynamic link creation\" --k 8 --lang typescript"
