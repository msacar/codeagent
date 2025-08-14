# CodeAgent - Tree-sitter Code Indexing with CocoInsight

A Tree-sitter powered, incremental code RAG indexer with CocoIndex + pgvector, now with **CocoInsight** integration for live pipeline monitoring and **Aider-style PageRank** for code importance ranking.

## Features

- 🌳 Tree-sitter based code parsing for accurate symbol extraction
- 🔄 Incremental indexing with CocoIndex
- 📊 Live pipeline monitoring with CocoInsight
- 🔍 Hybrid search (lexical + vector) with pgvector
- 🧮 Aider-style PageRank over defs/refs (name-based), stored back into chunks
- 🚀 Support for TypeScript, JavaScript, Python
- 👁️ Real-time visualization of indexing flow
- 🎯 **PageRank-based code importance ranking** (Aider-style)
- 🗺️ **Repository map generation** showing key code elements

## Setup

### Prerequisites

- PostgreSQL with pgvector extension
- Python 3.11+

### Installation

```bash
# Install the package
pip install -e .

# Or using make
make install
```

### Configuration

Create a `.env` file in the project root:

```env
CODEAGENT_ROOT=/path/to/your/codebase
COCOINDEX_DATABASE_URL=postgres://cocoindex:cocoindex@localhost/cocoindex
```

### Database Setup

Initialize the CocoIndex database schema:

```bash
make setup
# Or: python -c "from codeagent.pipeline.flow import build_index; import cocoindex; cocoindex.init(); build_index.setup(report_to_stdout=True)"
```

## Usage

### Basic Indexing

Run the indexing pipeline:

```bash
make index
# Or: python -c "from codeagent.pipeline.flow import run_index; run_index()"
```

This will also compute and store **PageRank** for your repo (file-level, Aider-style name matching).
You can print the top results:

```bash
codeagent pagerank --root $CODEAGENT_ROOT --top-n 50
```

### Aider-style repo-map knobs

You can tune the **lines-of-interest** condenser and token budget similar to Aider:

```bash
# Use a ~1000 token budget for each condensed symbol body (Aider default for repo map)
codeagent index --map-tokens 1000

# Adjust window padding around anchors and max lines per symbol
codeagent index --loi-pre 2 --loi-post 12 --loi-max-lines 120

# Highlight anchor lines in condensed code (purely visual)
codeagent index --loi-hilite --loi-mark "▶"
```

All flags can also be set via env vars:

```
CODEAGENT_MAP_TOKENS=1000
CODEAGENT_LOI_PRE=2
CODEAGENT_LOI_POST=12
CODEAGENT_LOI_MAX_LINES=120
CODEAGENT_LOI_HILITE=1
CODEAGENT_LOI_MARK=▶
```

> These knobs mirror Aider's approach of optimizing a repo map to a token budget and showing "lines of interest." See the Aider docs/blog for details.

### Live Monitoring with CocoInsight

Start the CocoInsight server to monitor your pipeline in real-time:

```bash
# Using make (recommended)
make insight

# Or using the CLI directly with main.py shim
cocoindex server -ci main.py --address 0.0.0.0:3000 --reload

# Or point directly at the flow file
cocoindex server -ci codeagent/pipeline/flow.py --address 0.0.0.0:3000 --reload
```

Then open **https://cocoindex.io/cocoinsight** in your browser. The UI will:
- Connect to your local server at port 3000
- Show the flow graph on the right
- Display step-by-step data preview on the left
- Allow you to click any field to inspect lineage

### Watch Mode

Auto-reindex on file changes:

```bash
make watch
```

### PageRank Analysis

Compute PageRank scores to identify the most important files and symbols:

```bash
# Compute and display PageRank results
codeagent pagerank --root /path/to/repo

# Show top 20 files and symbols
codeagent pagerank --top-n 20

# Save PageRank results for later use
codeagent pagerank --save-ranks ranks.json

# Load pre-computed ranks
codeagent pagerank --load-ranks ranks.json
```

### Repository Map

Generate an Aider-style repository map showing key code elements:

```bash
# Generate repository map
codeagent repomap --root /path/to/repo

# Focus on specific files
codeagent repomap --focus-files src/main.py src/utils.py

# Control map size
codeagent repomap --max-tokens 3000
```

The repository map uses PageRank to identify and display:
- Top files by importance
- Key symbols with contextual code snippets
- Dependencies between code elements

## Available Commands

```bash
make help        # Show all available commands
make install     # Install dependencies
make setup       # Initialize database schema
make index       # Run indexing pipeline
make insight     # Start CocoInsight server
make watch       # Watch for changes and auto-reindex
make clean       # Clean cached data
make test        # Run tests

# CLI commands
codeagent index           # Run indexing pipeline
codeagent query --q TEXT  # Search indexed code
codeagent pagerank        # Compute PageRank scores
codeagent repomap         # Generate repository map
codeagent watch           # Watch mode for auto-indexing
```

## Architecture

The pipeline follows this flow:

1. **Source Files** → Tree-sitter parsing
2. **Symbols** → Extract definitions and references
3. **PageRank** → Build dependency graph and compute importance scores
4. **Chunks** → Create semantic code units with importance ranks
5. **Embeddings** → Generate vector representations
6. **Storage** → Store in PostgreSQL with pgvector

CocoInsight provides real-time visibility into each step of this pipeline.

### PageRank Implementation (Aider-style)

The PageRank implementation follows Aider's approach:

- **Definition/Reference Tracking**: Parses code using Tree-sitter to extract symbol definitions and references
- **Dependency Graph**: Builds a directed graph where edges go from files that reference symbols to files that define them
- **Edge Weighting**: Uses heuristics like case style matching (camelCase vs snake_case) and symbol frequency
- **PageRank Calculation**: Runs the PageRank algorithm to identify important files and symbols
- **Repository Map**: Generates contextual code snippets for the most important elements

## Project Structure

```
codeagent/
├── codesitter/         # Tree-sitter parsing logic
├── pipeline/           # CocoIndex pipeline operations
│   ├── flow.py        # Main pipeline definition
│   ├── ops_parse.py   # Parsing operations
│   ├── ops_chunks.py  # Chunking operations
│   ├── ops_pagerank.py # PageRank operations
│   └── batch_pagerank.py # Batch PageRank processor
├── search/            # Retrieval logic
├── queries/           # Tree-sitter query files
├── pagerank.py        # Core PageRank implementation
└── repomap.py         # Repository map generator
```

## Notes

- The server automatically handles incremental updates
- Zero data retention with CocoInsight - it only visualizes your local pipeline
- If you see "setup not up-to-date" warnings, run `make setup` again

## Troubleshooting

If you encounter issues:

1. Ensure PostgreSQL is running with pgvector extension
2. Check your `.env` file has correct database credentials
3. Run `make setup` to ensure database schema is initialized
4. For CocoInsight issues, ensure port 3000 is available
5. Verify language queries are loaded: `make test-queries`

### Verifying Language Support

To check if Tree-sitter queries are properly loaded:

```bash
make test-queries
# Or: python test_queries.py
```

This will show if TypeScript, JavaScript, and Python queries are loaded correctly.

If you see empty symbols when indexing, check that the queries are present in:
- `codeagent/queries/tree-sitter-language-pack/`

## Contributing

See PLAN.md for the detailed architecture and design decisions.
