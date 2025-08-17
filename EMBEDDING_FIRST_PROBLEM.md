Great question. Here’s what I meant, and how it ties back to Aider—and to your current CodeAgent behavior.

# What “graph-rank + lexical (not embedding-first)” means

* **Graph-rank (PageRank over your code graph)**
  Build a directed graph where files point to the files they reference (defs ⇄ refs from Tree-sitter). Run PageRank and use that score to prefer definitions that live in “important” files. This is how Aider decides what parts of the repo make it into the map. ([Aider][1])

* **Lexical match (exact/substring on identifiers & paths)**
  For an identifier query like `getDynamicInstance`, boost results whose **symbol name** equals/contains the token, and lightly boost when the **file path** contains it. Aider’s map surfaces key *definitions* (class/method/function signatures) rather than whatever has the closest vector embedding. ([Aider][2])

* **Not embedding-first**
  “Embedding-first” means you rank by vector similarity (query→chunk) and only use other signals as tie-breakers. Aider’s repo-map selection is the opposite: **graph + lexical** decide what to show; embeddings aren’t the primary selector (Aider doesn’t describe using them for map selection at all). ([Aider][1])

# What Aider uses as data to rank & select

1. **Tree-sitter captures** of **definitions** and **references** (from `*-tags.scm`) to know where symbols are defined and used. ([Aider][1])
2. A **dependency graph** built from those refs, then **PageRank** to score file importance. ([Aider][1], [networkx.org][3])
3. A **token budget** (`--map-tokens`) to emit only the “critical lines” for high-value definitions. Aider treats this as a sizing control for the map it sends along with prompts. ([Aider][2], [GitHub][4])

# What CodeAgent is using right now (and the change we proposed)

* Your current `query` path behaves **embedding-first** (that’s why a short **type alias** can outrank the **method** you actually want).
* The fix we proposed: detect **identifier-style** queries and switch to:

  ```
  score = 0.25 * PageRank(file)
        + 0.70 * [exact name match]
        + 0.35 * [substring in name]
        + 0.15 * [substring in file path]
        + 0.20 * [kind bonus for method/function/ctor]
        - 0.10 * [penalty for type/enum]
        + 0.05 * [embedding tie-breaker]   # optional; set to 0 for strict Aider behavior
  ```

  …and **filter to definitions** (repo-map style) before ranking. This matches Aider’s “pick important defs by graph + lexical and then show their critical lines under a token budget.” ([Aider][1])

# TL;DR

* **Aider**: Captures → defs/refs → dependency graph → PageRank → pick high-value **definitions** → show **critical lines** within `--map-tokens`. No embedding-first ranking. ([Aider][1])
* **CodeAgent (today)**: Your `query` path is **embedding-first**.
* **Recommended**: For identifier lookups, switch to **graph-rank + lexical** (defs-only), with embeddings only as a tiny tie-breaker (or zero) to get 1:1 Aider behavior.

[1]: https://aider.chat/2023/10/22/repomap.html?utm_source=chatgpt.com "Building a better repository map with tree sitter"
[2]: https://aider.chat/docs/repomap.html?utm_source=chatgpt.com "Repository map"
[3]: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html?utm_source=chatgpt.com "pagerank — NetworkX 3.5 documentation"
[4]: https://github.com/paul-gauthier/aider/issues/752?utm_source=chatgpt.com "Repository map token limit not respected · Issue #752"
