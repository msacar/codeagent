# Context Map Feature

The context map feature provides a chat-aware repository map using personalized PageRank, similar to Aider's approach. It optimizes the repository map for the current chat context by:

1. **Seeding PageRank** with files and symbols mentioned in your prompt
2. **Personalizing the graph ranking** to prioritize relevant code
3. **Respecting token budgets** to provide concise, focused context

## Usage

```bash
# Basic usage with a prompt
python -m codeagent.cli context --root . --q "add feature to dynamic link creation"

# Seed with specific files you're working on
python -m codeagent.cli context --root . \
  --q "add validation to user service" \
  --file src/services/userService.ts \
  --file src/validators/userValidator.ts

# Exclude type declarations and tests for runtime focus
python -m codeagent.cli context --root . \
  --q "optimize database queries" \
  --exclude "**/*.d.ts" "**/@types/**" "**/__tests__/**" \
  --map-tokens 1500

# Include only specific file types
python -m codeagent.cli context --root . \
  --q "refactor authentication flow" \
  --include "**/*.py" "**/*.ts" \
  --top-files 30
```

## Options

- `--q PROMPT`: Your query/prompt to seed the context
- `--file FILE`: Explicitly seed with a file (can be repeated)
- `--map-tokens N`: Token budget for the context map (default: 1000)
- `--top-files N`: Maximum files to include (default: 25)
- `--include PATTERN`: Glob patterns to include
- `--exclude PATTERN`: Glob patterns to exclude

## How It Works

1. **Graph Construction**: Builds a dependency graph from code definitions and references
2. **Seed Extraction**: Identifies files and symbols mentioned in your prompt
3. **Personalized PageRank**: Runs PageRank biased toward your seed files
4. **Token-Aware Output**: Generates a concise map within your token budget

The context map shows:
- Ranked files by relevance to your query
- Key symbols from each file with brief context
- Approximate token usage

This feature is particularly useful for:
- Getting oriented in a new codebase
- Understanding dependencies for a specific feature
- Preparing context for LLM-assisted coding
- Identifying the most relevant files for a task
