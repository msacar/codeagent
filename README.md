# CodeAgent - Tree-sitter Code Indexing with CocoInsight

A Tree-sitter powered, incremental code RAG indexer with CocoIndex + pgvector, now with **CocoInsight** integration for live pipeline monitoring.

## Features

- 🌳 Tree-sitter based code parsing for accurate symbol extraction
- 🔄 Incremental indexing with CocoIndex
- 📊 Live pipeline monitoring with CocoInsight
- 🔍 Hybrid search (lexical + vector) with pgvector
- 🚀 Support for TypeScript, JavaScript, Python
- 👁️ Real-time visualization of indexing flow

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
```

## Architecture

The pipeline follows this flow:

1. **Source Files** → Tree-sitter parsing
2. **Symbols** → Extract definitions and references
3. **Chunks** → Create semantic code units
4. **Embeddings** → Generate vector representations
5. **Storage** → Store in PostgreSQL with pgvector

CocoInsight provides real-time visibility into each step of this pipeline.

## Project Structure

```
codeagent/
├── codesitter/         # Tree-sitter parsing logic
├── pipeline/           # CocoIndex pipeline operations
│   ├── flow.py        # Main pipeline definition
│   ├── ops_parse.py   # Parsing operations
│   └── ops_chunks.py  # Chunking operations
├── search/            # Retrieval logic
└── queries/           # Tree-sitter query files
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
