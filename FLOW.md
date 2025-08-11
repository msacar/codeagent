totally—here’s the full tour of our pipeline, end-to-end, with what runs where and why.

# Big picture

**Goal:** turn a repo into **searchable, semantically rich code chunks** for a coding agent.
**Stack:** Aider-style Tree-sitter parsing → structured symbols → high-quality chunks → embeddings → **Postgres+pgvector** via **CocoIndex**.
**Live debugging/insight:** CocoInsight UI on top of the CocoIndex server.

# 0) Inputs & config

* **Root path:** `CODEAGENT_ROOT` (in `.env`). The CLI also accepts `--root` and we set the env in `main.py` for the server case.
* **DB:** `COCOINDEX_DATABASE_URL=postgres://cocoindex:cocoindex@localhost/cocoindex`.
* **Languages:** TypeScript, JavaScript, Python (more later).
* **Queries:** Aider’s `.scm` files:

  * We **prefer** `queries/tree-sitter-languages/{lang}-tags.scm`.
  * Fallback to `queries/tree-sitter-language-pack/` if needed.
  * We **skip** empty/comment-only SCMs to avoid silent no-ops.
* **Tree-sitter versions:** we mirror Aider’s setup:

  * `tree-sitter==0.24.*`, `tree-sitter-language-pack==0.8.*`, `grep-ast==0.9.0`
  * We use `grep_ast.tsl` (`get_language`, `get_parser`, `USING_TSL_PACK`) just like Aider.

# 1) Source: files into the flow

In `build_index` (our CocoIndex `@flow_def`):

* We add a `LocalFile` source over `CODEAGENT_ROOT` with include/exclude globs for `*.ts, *.tsx, *.js, *.jsx, *.py` (ignores `node_modules`, `dist`, etc.).
* This gives us a per-file row with at least:

  * `filename` (repo-relative path)
  * `content` (string with file text)

# 2) Parse: text → symbols (Aider style)

**Op:** `parse_file_to_symbols(content: str, filename: str) -> str` (JSON)

How it works under the hood:

* **Grammar & parser:** `grep_ast.tsl.get_language(lang)` and `get_parser(lang)` based on the filename extension.
* **Load query text:** from our `queries/.../{lang}-tags.scm` with the preference rules above.
* **Run the query:** `language.query(qsrc).captures(tree.root_node)`

  * If `USING_TSL_PACK` is true, that call returns `{capture_name: [nodes...]}`; we normalize to a flat list of `(node, capture_name)` pairs like Aider does.
* **Materialize Aider-like captures into records:**

  * We detect **definitions** via `@definition.*` captures (e.g., `@definition.class`, `@definition.function`, `@definition.method`, `@definition.constructor`).
  * We extract **names** via `@name.definition.*` (identifier text).
  * We collect optional **doc comments** via the `@doc` capture (when present), already trimmed/adjacent-selected by the `.scm` predicates.
  * We compute **spans** (start/end line/byte) from the AST node.
  * We infer **container** (e.g., a method’s parent class) when the grammar allows.
  * We collect **references** from `@reference.*` captures (e.g., `@reference.call`), which later become `deps` for ranking/context.
* **Return value:** a JSON string:

  ```json
  {
    "defs": [
      {"lang":"ts","symbol_kind":"class|function|method|...","name":"Foo","start_line":…,"end_line":…,"container":…,"doc":…}
    ],
    "refs": [
      {"name":"someCall","line":…}
    ]
  }
  ```

**Why JSON?** CocoIndex’s op type system is strict about table schemas; serializing the inter-op payload as JSON is robust and simple. We parse it in the next step.

# 3) Chunk: symbols → chunks (our RAG units)

**Op:** `symbols_to_chunks(syms_json: str, filename: str, content: str) -> list[Chunk]`
`Chunk` is a `@dataclass` (so CocoIndex sees a **Struct**):

* **Stable ID:** `stable_id(file, name, symbol_kind, start_line, end_line)` → content-insensitive identity that’s deterministic for the same symbol span.
* **Header + Body:**

  * `header` = `"path:Ls  kind name"` (compact, human-readable).
  * `body` = the minimal source slice for the def **plus a bit of trailing context**:

    * we pad longer (e.g., `+12` lines) for functions/methods/constructors, less for classes/types—this mirrors Aider’s “repomap” idea: just enough to understand the symbol.
  * If we captured a `doc` comment, it’s prefixed into `body`.
* **Text to embed:** `text = header + "\n" + body` (stored too).
* **Deps:** unique set of referenced identifiers from the file’s refs (light-weight for now; can later resolve across files).
* **SHA:** file content hash (for lineage / change detection; not in the ID, but stored).
* **Fields per chunk:**

  ```
  id, file, abs_file, lang, symbol_kind, name, container,
  start_line, end_line, header, body, deps, rank, sha, text
  ```

  `rank` is 0.0 now (slot for PageRank later).

# 4) Embed: chunk text → vector

**Transform flow:**
`chunk_text_to_embedding(text: cocoindex.DataSlice[str]) -> cocoindex.DataSlice[list[float]]`

* Uses `cocoindex.functions.SentenceTransformerEmbed(model="sentence-transformers/all-MiniLM-L6-v2")`.
* You can later switch to Voyage (`voyage-code-3`) by swapping the transform.

In the main flow we do:

```python
with f["chunks"].row() as ch:
    ch["embedding"] = ch["text"].call(chunk_text_to_embedding)
```

# 5) Store: write to Postgres + pgvector

We export a collector named `out`:

* **Target:** `cocoindex.targets.Postgres()`
* **Table name:** generated from the flow, defaulting to something like `codeindex__code_chunks`.
* **Primary key:** `["id"]` (the stable ID we made).
* **Vector index:** on `embedding` with **cosine** similarity.

CocoIndex handles the upsert/DDL. On first run you either call:

* `build_index.setup()` (we do this in `run_index()` now), or
* CLI: `cocoindex setup`.

# 6) Flow wiring (how the pieces connect)

Inside `build_index`:

```python
with data_scope["files"].row() as f:
    f["symbols"] = f["content"].transform(parse_file_to_symbols, filename=f["filename"])
    f["chunks"]  = f["symbols"].transform(symbols_to_chunks, filename=f["filename"], content=f["content"])

    with f["chunks"].row() as ch:
        ch["embedding"] = ch["text"].call(chunk_text_to_embedding)
        out.collect(
          id=ch["id"], file=f["filename"], lang=ch["lang"], symbol_kind=ch["symbol_kind"], …
          header=ch["header"], body=ch["body"], text=ch["text"], deps=ch["deps"], sha=ch["sha"],
          embedding=ch["embedding"]
        )
```

Think of it like a small DAG:

```
LocalFile → (parse_file_to_symbols) → symbols
symbols + content → (symbols_to_chunks) → chunks
chunks.text → (chunk_text_to_embedding) → embeddings
chunks + embeddings → Postgres
```

# 7) Incremental behavior

We get “incremental enough” in 3 ways:

* **CocoIndex source:** only changed files re-flow (depending on its source hashing/mtime).
* **Stable PK (`id`)**: unchanged symbol spans result in **no DB changes**.
* **`sha` field:** lets you detect when a chunk’s source changed even if the span stayed put.

Future niceties (easy to add later):

* Do a **file diff** and only re-embed chunks whose spans overlap changes.
* Use `QueryCursor` range querying for huge files (once we move off 0.24).

# 8) CocoInsight (live UI)

* Start: `cocoindex server -ci main.py --address 0.0.0.0:3000 --reload`
* Open the Insight UI (it connects to your local server) to see:

  * the **graph** of sources/ops/collectors,
  * **sample rows** for every node,
  * live logs/warnings (e.g., missing queries).

# 9) What you can tweak per project

* **Queries**: adjust SCMs to capture more symbol kinds (enums, interfaces, types, exports, etc.). You already have JS/TS/Py from Aider; we can add more.
* **Chunking policy**: change the context padding heuristics by kind, or include sibling nodes.
* **Embedding**: switch models, add a code-aware re-ranker later.
* **Storage**: add extra indexes (filename, lang, symbol\_kind) for fast filters.

---

If you want, I can generate a short README for the repo with these steps + commands, or add a `make insight` / `make index` to speed up your loop.
