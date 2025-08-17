Yes. Here’s a crisp parity-plus plan that makes CodeAgent do **everything Aider does** for the repo-map/defs-refs pipeline — and keep CodeAgent’s extra goodies (like `symbol_kind`, RAG retrieval) on top.

# What Aider does (sources)

* Builds a repo-map from **Tree-sitter captures** (`tags.scm`): collect **definitions** and **references**, then select the key lines to show. No per-language Python taxonomy; the capture names carry the semantics. ([aider.chat][1])
* **Switched from ctags to Tree-sitter**; relies on prebuilt language packs to scale coverage. ([aider.chat][2])
* Language expansion via **tree-sitter-language-pack** (bulk tags files). ([aider.chat][3], [GitHub][4])
* Picks “what matters” via a **defs↔refs dependency graph** and **PageRank**, then emits compact “lines of interest” per top file/symbol under a token cap. ([aider.chat][1])

# Where CodeAgent stands today (from your snapshot)

* You already use `tags.scm` captures like `@definition.function`, `@definition.method`, `@reference.call` in the bundled queries.  &#x20;
* Pipeline: parse → make chunks → embed → store in Postgres (`code_chunks`) with an optional `rank` column. &#x20;
* Current search orders by **embedding distance** then rank (PageRank is only a tiebreak).&#x20;
* Your notes show an **Aider-style PageRank + repomap module** designed/added (graph of defs→refs, token-budget map). &#x20;

# Parity checklist — Aider → CodeAgent (status & actions)

1. **Capture-driven parsing (no per-language Python logic)**
   Aider trusts capture names (`name.definition.*` / `name.reference.*`).
   **CodeAgent:** keep your captures; make the normalizer “capture-first” and treat class/method/function/etc. straight from the capture tag. Keep `symbol_kind` as a **bonus field** (Aider doesn’t keep it, but it helps your UX). ([aider.chat][1])&#x20;

2. **Faux-refs when a language lacks refs**
   Aider tokenizes when queries give only defs so the graph isn’t empty.
   **CodeAgent:** already mirrors this (token backfill); keep it.&#x20;

3. **Dependency graph + PageRank → select important code**
   Aider ranks files/symbols with PageRank on the cross-file refs graph, then emits compact snippets. ([aider.chat][1])
   **CodeAgent:** wire your implemented PageRank to persist per-file scores and use them both for (a) the **repomap** and (b) **query ranking** (see #4).&#x20;

4. **Def-first scoring for identifier queries (Aider-like behavior)**
   Aider’s map doesn’t use embeddings to choose which defs to show; it uses graph importance. ([aider.chat][1])
   **CodeAgent:** add a **def-only fast path** for `codeagent query` when the user searches an identifier:

   * `WHERE is_def = TRUE AND name ILIKE :tok`
   * `ORDER BY (file_pr * (1 + 0.2*def_refcount)) DESC`
     Fall back to hybrid (PageRank + lexical + embeddings) only when the user’s query is natural language. This fixes cases where a short **type alias** outranks the **method** you actually want.&#x20;

5. **“Lines of interest” condensation**
   Aider prints concise, context-rich lines per selected def. ([aider.chat][5])
   **CodeAgent:** replace the fixed body slice with an **LOI condenser** (few lines of pre/post plus in-body matches) when emitting the repo-map text. (Your chunking already includes headers/containers; LOI will reduce tokens while keeping signal.)&#x20;

6. **Queries search path & language pack**
   Aider prefers queries from **tree-sitter-language-pack**, then falls back to its bundled set. ([aider.chat][6])
   **CodeAgent:** keep your env-override + packaged queries approach, and **vendor the language-pack tags** so coverage matches Aider’s out of the box.  ([GitHub][4])

7. **UX differences (keep CodeAgent’s enhancements)**

* Keep `symbol_kind` in the DB/CLI: Aider doesn’t surface it, but it’s handy for headers/snippet rules and filtering.
* Keep your **RAG retrieval** path (embeddings) for NL questions, but **don’t** let it dominate identifier lookups where Aider would show a def from the map.

# “All Aider does + more” — concrete accepts/diffs to land

* **Parser (capture-first kinds):** Switch `_normalize_kind` to derive from capture (retain `symbol_kind` for printing).
* **Graph & ranks:** Confirm per-file PageRank is persisted (e.g., `code_chunks.rank` or a `files` table) and expose `codeagent pagerank` / `codeagent repomap` commands as in your notes.&#x20;
* **Query scoring:** Add a **def-only, PR-weighted** SQL for identifier tokens; keep current vector query as a fallback for descriptive NL.&#x20;
* **LOI condenser:** Replace fixed `slice_body` with an LOI renderer in the repo-map output (keep token budget knob like `--map-tokens`). ([aider.chat][5])
* **Bundle tags:** Pull **tree-sitter-language-pack** tags so “supported languages” parity is straightforward; still allow `CODEAGENT_QUERIES_DIR` overrides. ([GitHub][4])

---

## Quick comparison table

| Area                 | Aider                                                          | CodeAgent now                                          | Change to match Aider (keep enhancements)                                 |
| -------------------- | -------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------- |
| Captures → defs/refs | `tags.scm` (`@definition.*`, `@reference.*`) ([aider.chat][1]) | Same, but with Python `METHOD_LIKE`/etc. normalization | Make kinds **capture-first**; keep `symbol_kind` only as extra metadata.  |
| Faux-refs            | Tokenize when refs missing                                     | Implemented                                            | Keep as-is.                                                               |
| Importance           | Graph of cross-file refs → **PageRank** → top map              | Implemented module/notes; rank column present          | Use PR in **repomap** and **identifier query** ordering.                  |
| Map text             | “Lines of interest” to fit token cap ([aider.chat][5])         | Fixed body slices around defs                          | Add **LOI condenser** + `--map-tokens`.                                   |
| Language scale       | **tree-sitter-language-pack**                                  | Custom queries + overrides                             | Vendor the language-pack tags; keep env override. ([GitHub][4])           |
| Retrieval            | Map selection doesn’t use embeddings                           | Vector top-k first, then rank                          | **Def-first** PR/lexical scoring for identifiers; use vectors for NL.     |

---

If you like, I can draft the exact diffs for:

* `_normalize_kind` (capture-first),
* `retriever.search()` (def-first + PR), and
* a small `repomap` emitter with an LOI condenser (token-budget aware).

Either way, with the steps above, CodeAgent will have **full Aider parity** (captures → graph → PageRank → concise map) while preserving CodeAgent-specific enhancements like `symbol_kind` and a better RAG mode for natural-language queries. ([aider.chat][1])

[1]: https://aider.chat/2023/10/22/repomap.html?utm_source=chatgpt.com "Building a better repository map with tree sitter - Aider"
[2]: https://aider.chat/docs/ctags.html?utm_source=chatgpt.com "Improving GPT-4's codebase understanding with ctags - Aider"
[3]: https://aider.chat/docs/recordings/tree-sitter-language-pack.html?utm_source=chatgpt.com "Add language support via tree-sitter-language-pack"
[4]: https://github.com/Goldziher/tree-sitter-language-pack?utm_source=chatgpt.com "Goldziher/tree-sitter-language-pack"
[5]: https://aider.chat/docs/repomap.html?utm_source=chatgpt.com "Repository map - Aider"
[6]: https://aider.chat/docs/languages.html?utm_source=chatgpt.com "Supported languages"



Here’s a side-by-side of what **CodeAgent** does today vs. what **Aider** does, focusing on parsing, symbol kinds, repo-map/ranking, and retrieval. I’ll point to the exact spots in your two snapshots.

# 1) How each parses code & finds symbols

**Aider**

* Uses Tree-sitter queries (`{lang}-tags.scm`) that already tag things like `@definition.function`, `@definition.method`, `@definition.class`, and `@reference.call`. It normalizes purely from the **capture names** (`name.definition.*` → def, `name.reference.*` → ref). &#x20;
* Its shipped queries show those tags directly (examples from multiple languages in the repo). &#x20;

**CodeAgent**

* Also runs `{lang}-tags.scm`, but then applies a **Python-side normalization** layer to map Tree-sitter node types to a consistent `symbol_kind` across languages (e.g., class/function/method/constructor/type/etc.). That’s what those `METHOD_LIKE`, `FUNCTION_LIKE`, `CLASS_LIKE`, … sets are for. &#x20;
* Loads queries with a clear precedence (env override dir, then packaged dirs), similar in spirit to Aider’s `get_scm_fname` search path.&#x20;

👉 **Why CodeAgent has those `METHOD_LIKE` / `FUNCTION_LIKE` sets (and Aider doesn’t):**
Aider relies on the query files to emit precise captures like `@definition.method` vs `@definition.function`, so it can infer kinds straight from capture names. CodeAgent adds a normalization pass based on **node types** to ensure consistent `symbol_kind` even if a query emits a more generic capture; it also needs the kind downstream (e.g., for body padding), and for Python it distinguishes “method vs top-level function” by inspecting the **container** class, hence the special comment for Python in `METHOD_LIKE`.&#x20;

# 2) Defs/refs & “faux-refs”

**Aider**

* If a language’s queries only yield **defs** but not **refs**, Aider **backfills refs** by tokenizing identifiers (Pygments) so the graph isn’t empty.&#x20;

**CodeAgent**

* Implements the same idea: when it sees defs but no refs, it tokenizes and adds **faux-refs** (line = `-1`).&#x20;

# 3) Containers (class owners) and docs

**Aider**

* Relies on `tags.scm` structure and “lines of interest” rendering later (see repo-map section below).&#x20;

**CodeAgent**

* Walks up the AST to find the **enclosing class name** to set `container` for definitions—useful for later chunk headers and retrieval.&#x20;
* Associates adjacent `@doc` capture to the next definition; your queries include `@doc` patterns (JS/TS/Py examples). &#x20;

# 4) Turning defs/refs into chunks

**Aider**

* The repo map shows compact **“lines of interest”** around important defs using `TreeContext` (not full bodies unless the file is added to chat).&#x20;

**CodeAgent**

* Emits per-symbol chunks with a small **body slice** (padding depends on kind; functions/methods get more). That’s why normalized `symbol_kind` matters. &#x20;
* Each chunk has: header `"{file}:L{start}  {symbol_kind} {name}"`, body, `deps` (from refs), etc., ready for embedding.&#x20;

# 5) Ranking & repo map behavior

**Aider**

* Builds a **graph of defs ↔ refs** and runs **PageRank** to choose the most important code to show in the repo map. It then renders compact snippets per ranked file.&#x20;
* UX-wise, the user adds full files to chat; the rest of the repo is summarized by this map.&#x20;

**CodeAgent**

* Your snapshot shows the **embedding/flow** and **retrieval** plumbing already, and a search that sorts by **vector distance then rank** (when present). The rank slot is where a PageRank pass can plug in.&#x20;
* (Per your own PageRank notes: you’ve planned/added an Aider-style graph pass and repo-map generator to integrate with chunking.) &#x20;

# 6) Query loading and language coverage

**Aider**

* Prefers its **language-pack** queries and falls back to **languages** queries; adding a language is mostly “provide a good `{lang}-tags.scm`”.&#x20;

**CodeAgent**

* Mirrors that idea and adds an ENV override (`CODEAGENT_QUERIES_DIR`) so you can drop updated queries without changing code.&#x20;

---

## TL;DR — Concrete differences

* **Why those METHOD/FUNCTION/CLASS sets exist in CodeAgent:**
  You normalize **node types → `symbol_kind`** in Python to keep kinds consistent across languages and to drive chunk formatting (padding) and container logic—Aider mostly **trusts the query tags** and doesn’t need an extra mapping layer.&#x20;

* **Similarity to Aider’s behavior you already replicate:**
  *tags.scm* capture walk, **defs/refs**, **faux-refs**, container detection, query-loading precedence—these all match Aider’s approach closely.  &#x20;

* **Where CodeAgent currently differs in UX:**
  Aider’s CLI/chat flow always sends **full text** of “added” files + a **trimmed, ranked repo map** for the rest; CodeAgent’s snapshot shows per-symbol **chunks** with short bodies optimized for RAG retrieval, sorted by **vector score, then rank** (once PageRank is in). &#x20;

If you want, I can generate a small patch to:

1. make the normalization optional when the query already emits precise kinds (so you can lean even more on `@definition.method`/`function`), and
2. add the repo-map render step (rank → compact “lines of interest”) to mirror Aider’s map exactly.



