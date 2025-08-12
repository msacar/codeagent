# PR: Implement Aider-style PageRank for Code Analysis

## Summary
Implemented PageRank-based code importance ranking following Aider's proven approach. This enhancement adds intelligent code ranking to improve RAG retrieval quality and provides repository maps for better code understanding.

## Changes

### Core Implementation
- **`codeagent/pagerank.py`**: Core PageRank engine with dependency graph building
- **`codeagent/pipeline/batch_pagerank.py`**: Batch processor for repository-wide ranking
- **`codeagent/pipeline/ops_pagerank.py`**: Pipeline operations for PageRank integration
- **`codeagent/repomap.py`**: Repository map generator with token-aware output
- **`codeagent/pipeline/ops_chunks.py`**: Updated to include PageRank scores in chunks

### CLI Enhancements
- **`codeagent/cli.py`**: Added `pagerank` and `repomap` commands
- **`pyproject.toml`**: Added `networkx>=3.0` dependency

### Documentation
- **`README.md`**: Updated with PageRank features and usage examples
- **`PAGERANK_IMPLEMENTATION.md`**: Detailed implementation documentation
- **`FIXES_APPLIED.md`**: Documentation of critical fixes applied

### Tests
- **`test_pagerank.py`**: Comprehensive tests for PageRank functionality
- **`validate_fixes.py`**: Validation script for critical fixes

## Critical Fixes Applied
1. ✅ Added `pad_before` parameter to `slice_body` function
2. ✅ Fixed off-by-one error in line number display (0-based to 1-based)
3. ✅ Corrected frequency dampening order in PageRank weights
4. ✅ Fixed exclusion pattern matching using `fnmatch`

## Features
- 🎯 **Automatic Code Ranking**: Identifies important files and symbols using PageRank
- 🗺️ **Repository Maps**: Generates Aider-style contextual code maps for LLMs
- 📊 **Dependency Graphs**: Builds directed graphs from symbol definitions/references
- 🔧 **Smart Weighting**: Uses naming conventions and frequency heuristics
- 💾 **Rank Caching**: Can save/load computed ranks for efficiency

## Usage Examples

```bash
# Compute PageRank for repository
codeagent pagerank --root /path/to/repo --top-n 20

# Generate repository map
codeagent repomap --max-tokens 3000

# Save ranks for later use
codeagent pagerank --save-ranks ranks.json
```

## Testing
All tests pass with the applied fixes:
- Core PageRank functionality ✓
- Batch processing ✓
- Repository map generation ✓
- Edge case handling ✓

## Impact
- **Better RAG Retrieval**: Higher-ranked code gets priority in search results
- **Improved Code Understanding**: Automatically identifies key files and symbols
- **LLM Context Optimization**: Repository maps provide focused context within token limits

## Implementation Notes
- Follows Aider's documented approach for definitions/references tracking
- Uses NetworkX for graph operations with standard PageRank parameters (α=0.85)
- Integrates seamlessly with existing CocoIndex pipeline
- Maintains backward compatibility with existing functionality

## Next Steps
- Consider real-time PageRank updates during incremental indexing
- Add visualization of dependency graphs in CocoInsight
- Explore language-specific ranking heuristics

---
This implementation brings enterprise-grade code ranking capabilities to the codeagent project, matching the proven patterns from Aider while integrating smoothly with the CocoIndex architecture.
