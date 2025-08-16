#!/bin/bash
set -e

echo "🔧 Re-installing codeagent package (picks up dataclass changes)..."
cd /Users/mustafaacar/codeagent
pip install -e . > /dev/null 2>&1

echo "✅ Package reinstalled"
echo ""
echo "🧪 Running KTable value type fix test..."
python test_ktable_value_fix.py

echo ""
echo "📝 Ready to recreate/upgrade the flow schema and index:"
echo ""
echo "  codeagent index --root /Users/mustafaacar/retter/shortlink \\"
echo "    --map-tokens 1000 --loi-pre 2 --loi-post 12 --loi-hilite"
echo ""
echo "After indexing, you should see:"
echo "  - No KTable value errors"
echo "  - 'Updated PageRank on N chunk rows.' message"
echo ""
echo "Then test a query:"
echo "  codeagent query --root /Users/mustafaacar/retter/shortlink \\"
echo "    --q \"dynamic link creation\" --k 8 --lang typescript"
