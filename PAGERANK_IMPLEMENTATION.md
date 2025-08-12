# PageRank Implementation Summary

## Overview

Successfully implemented Aider-style PageRank functionality for the codeagent project. The implementation follows Aider's approach to rank code importance based on symbol definitions and references.

## Key Components Added

### 1. Core PageRank Module (`codeagent/pagerank.py`)
- `CodePageRank` class that builds dependency graphs from code
- Tracks symbol definitions and references
- Creates directed graph: referencer → definer
- Applies edge weighting based on:
  - Case style consistency (camelCase vs snake_case)
  - Symbol frequency (common symbols weighted less)
  - Symbol type (classes/types weighted more)
- Runs PageRank algorithm to compute importance scores

### 2. Batch Processing (`codeagent/pipeline/batch_pagerank.py`)
- `BatchPageRankProcessor` for processing entire repositories
- Scans all matching files and extracts symbols
- Computes global PageRank scores
- Can save/load ranks to JSON for caching
- Provides ranked lists of files and symbols

### 3. Repository Map (`codeagent/repomap.py`)
- `RepoMap` class for generating Aider-style repository maps
- Shows most important files and symbols
- Includes contextual code snippets
- Token-limited output for LLM contexts
- Supports focusing on specific files

### 4. Pipeline Integration (`codeagent/pipeline/ops_chunks.py`)
- Updated chunking operation to use PageRank scores
- Each code chunk now has an importance rank
- Falls back gracefully if PageRank not computed

### 5. CLI Commands (`codeagent/cli.py`)
New commands added:
- `codeagent pagerank` - Compute and display PageRank results
- `codeagent repomap` - Generate repository map

## How It Works

1. **Parsing Phase**: Tree-sitter extracts symbol definitions and references from code
2. **Graph Building**: Creates dependency graph where edges represent "uses" relationships
3. **Ranking**: PageRank algorithm identifies important files and symbols
4. **Integration**: Ranks are used when creating chunks for better RAG retrieval

## Usage Examples

```bash
# Compute PageRank for a repository
codeagent pagerank --root /path/to/repo --top-n 20

# Save ranks for later use
codeagent pagerank --save-ranks ranks.json

# Generate repository map
codeagent repomap --max-tokens 3000

# Focus on specific files
codeagent repomap --focus-files src/main.py src/utils.py
```

## Implementation Details

### Following Aider's Approach
- Simple def/ref tracking (not detailed symbol types)
- Backfills references using tokenizer if none found
- Graph edges weighted by naming conventions
- PageRank with damping factor 0.85

### Key Differences from Full Aider
- Integrated with CocoIndex pipeline
- Batch processing separate from main pipeline
- Simplified for initial implementation

## Testing

Run tests with:
```bash
python test_pagerank.py
```

## Dependencies Added
- `networkx>=3.0` for graph operations and PageRank

## Benefits

1. **Better Code Understanding**: Identifies key files and symbols automatically
2. **Improved RAG**: Higher-ranked code gets priority in retrieval
3. **Repository Maps**: Quick overview of codebase structure for LLMs
4. **Aider Compatibility**: Follows proven patterns from Aider

## Future Enhancements

- Real-time PageRank updates during indexing
- Cross-repository dependency tracking
- Language-specific ranking heuristics
- Integration with CocoInsight visualization
