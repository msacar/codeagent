Absolutely—now that I’ve re-read the **right** CodeAgent snapshot, here’s a fresh head-to-head with Aider, focused on repo-map/LOI, captures, and token budgeting.

# What Aider does (reference points)

* **Captures drive kinds**: Aider’s `*-tags.scm` emit captures like `@definition.function`, `@definition.method`, `@definition.class`, `@reference.call`; Aider interprets kinds straight from the capture names. ([Aider][1], [gitingest.com][2])
* **Repo map + token budget**: It builds a repo map of “critical lines,” prunes to fit a token budget (`--map-tokens`, default \~1k) and dynamically right-sizes the map. ([Aider][3], [GitHub][4])

# What CodeAgent (this branch) now does

**1) Capture-first symbol kinds (Aider-style) + container via captures**

* Parser: capture-first normalization (`definition.*`, `name.definition.*`) so kinds come from captures; special-cases constructor → “constructor.”&#x20;
* Container detection: finds the *smallest enclosing* captured class (`*.class`) to label a method’s `container`—language-agnostic. &#x20;
* When materializing defs, it calls `_enclosing_class_name` to attach `container`.&#x20;

**2) Aider-style “Lines of Interest” (LOI) condensing with token budget**

* `condense_symbol_body(...)` computes anchor windows (signature + references), merges windows, and truncates by **token budget** and `max_lines`. &#x20;
* The pipeline builds anchors from the signature and referenced identifiers and feeds the condenser; **token budget** is read from `CODEAGENT_MAP_TOKENS`, with LOI padding knobs in env. &#x20;
* The condenser itself does token estimation (uses `tiktoken` if available, else chars/4 heuristic).&#x20;

**3) PageRank integration like Aider’s repo-map ranking**

* After indexing, CodeAgent computes a weighted file PageRank (α=0.85) and updates chunk ranks; exposes “top files” and “top symbols.”  &#x20;
* Aider describes this kind of “optimize the map to fit the token budget using a graph ranking.” CodeAgent now matches that spirit.&#x20;

**4) tags.scm loader with Aider-like precedence**

* Looks for `*-tags.scm` in an override dir (`$CODEAGENT_QUERIES_DIR`) and in packaged queries; works with `tree-sitter-language-pack` too. &#x20;

**5) Pipeline uses captures → symbols → chunks → embeddings**

* `ops_chunks.py` turns symbols into header/body/dep chunks; ranks filled in after PR update; `stable_id` for deterministic IDs. &#x20;
* `spans.py` provides `slice_body` & `stable_id`.&#x20;

# Quick comparison (updated)

| Area                     | Aider                                                | CodeAgent (now)                                                              | Status/Notes                                                              |
| ------------------------ | ---------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **Kind detection**       | From capture names in `*-tags.scm`                   | **Capture-first** normalization; no hard node-type tables required for kinds | ✅ Matches Aider’s approach.                                               |
| **Method→class**         | Implicit via captured scopes                         | **Container from captures** (smallest enclosing `.class`)                    | ✅ Robust across grammars.                                                 |
| **Repo map/LOI**         | “Critical lines” + token budget                      | **LOI condenser** + token budget (`CODEAGENT_MAP_TOKENS`)                    | ✅ Parity on behavior; env knobs available.                                |
| **Token budget control** | `--map-tokens` (also env `AIDER_MAP_TOKENS`)         | Env only: `CODEAGENT_MAP_TOKENS` (+ `CODEAGENT_LOI_*`)                       | ⚠️ Suggest adding CLI `--map-tokens` for 1:1 UX. Aider docs: ([Aider][5]) |
| **Ranking**              | Graph ranks to pick most relevant content            | File PageRank + symbol scores; persisted back to chunks                      | ✅ Equivalent strategy.                                                    |
| **tags.scm sourcing**    | Ships many `*-tags.scm`, can pull from language pack | Loader supports override dir & packaged queries                              | ✅ Similar search path.                                                    |

# What (if anything) to change to be truly 1:1 with Aider

1. **Add CLI flag parity**
   Expose `--map-tokens` (and maybe `--loi-pre/--loi-post/--loi-max-lines`) in `codeagent cli` so users don’t have to set envs. Today it’s env-only (`CODEAGENT_MAP_TOKENS`, `CODEAGENT_LOI_*`).   Docs parity: ([Aider][5])

2. **(Optional) Show actual token usage in “context” views**
   Aider surfaces map size vs budget; you already compute approx token usage when building a “context map.” Keep or promote that path to the CLI.&#x20;

3. **(Already done)** Capture-first kinds + container by capture. This removes the need for the big language-specific `METHOD_LIKE/FUNCTION_LIKE/...` spreadsheets to determine symbol kind (they can stay only as *fallback metadata* if you want).&#x20;

---

### Bottom line

With this branch, CodeAgent now **matches Aider’s core repo-map mechanics** (capture-driven defs/refs, LOI condensation within a token budget, graph-ranked importance) and adds a solid pipeline + persistence. If we add a small CLI layer for `--map-tokens` (mirroring Aider’s UX), you’ll have true 1:1 behavior **plus** CodeAgent’s extra ergonomics.
Aider references for behavior & UX: blog on repomap and docs for `--map-tokens`. ([Aider][1])

If you want, I can draft the exact `argparse` diff to wire `--map-tokens` → `CODEAGENT_MAP_TOKENS`.

[1]: https://aider.chat/2023/10/22/repomap.html?utm_source=chatgpt.com "Building a better repository map with tree sitter"
[2]: https://gitingest.com/Aider-AI/aider?utm_source=chatgpt.com "Gitingest"
[3]: https://aider.chat/docs/repomap.html?utm_source=chatgpt.com "Repository map"
[4]: https://github.com/paul-gauthier/aider/issues/752?utm_source=chatgpt.com "Repository map token limit not respected · Issue #752"
[5]: https://aider.chat/docs/config/options.html?utm_source=chatgpt.com "Options reference"
