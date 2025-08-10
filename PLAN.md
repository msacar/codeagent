Perfect — let’s design the **full, production-ready pipeline** that mirrors (and extends) Aider’s Tree-sitter repo-map behavior, builds **incremental** indexes with CocoIndex, and lands everything in a vector DB for **RAG-compliant** retrieval.

I read the files you shared (notably `repomap.py`, `base_coder.py`, `main.py`, and your `typescript-tags.scm`). Quick takeaways that matter for our build:

* Aider loads a `{lang}-tags.scm`, runs **Tree-sitter** queries, and turns each capture into `Tag(rel_fname, fname, line, name, kind)` where `kind ∈ {def, ref}`. If a language only has **defs** (your TS tags file does), it **backfills refs via Pygments** tokenization so graphs still work.
* It builds a **defs↔refs graph** and PageRanks files/idents to decide what’s important, then renders **compact context snippets** per file (via `TreeContext`) for the LLM.
  We’ll replicate these ideas, but make them **indexable chunks** for vector search + hybrid retrieval.

---

# Architecture (bird’s-eye)

**Source** ➜ **Watcher** ➜ **Parser & Tagger** ➜ **(optional) Graph Rank** ➜ **Chunk Builder** ➜ **Embed** ➜ **Vector DB**
…and a **Retriever** that does **hybrid** (lexical + vector) with structure-aware expansion (container + neighbors).

Key design choices:

* **Queries:** Vendor Aider’s `*-tags.scm` per language (like your TS file). If a lang emits only `definition.*`, we **faux-ref** via Pygments (same trick Aider uses).
* **Incrementality:** Hash inputs + **mtime**; only reprocess dirty files; keep lineage (file ➜ tags ➜ chunks ➜ embeddings).
* **RAG hygiene:** Chunks are **semantic units** (class/method/function) with **source of truth** (file path + line span) and **rich metadata** for filters and stitching.

---

# Folder layout (opinionated)

```
codeagent/
  queries/
    tree-sitter-language-pack/
      typescript-tags.scm
      python-tags.scm
      ...
  codesitter/
    tags_loader.py          # load grammars & tags.scm
    ts_parser.py            # parse files, run queries -> Tag[]
    spans.py                # def→source span + context windows
    graph_rank.py           # optional PageRank on defs/refs
  pipeline/
    ops_parse.py            # CocoIndex ops: file -> Tag[]
    ops_chunks.py           # Tag[] -> Chunk[]
    ops_embed.py            # Chunk[] -> Embeddings
    ops_store.py            # write to pgvector (or other)
    flow.py                 # CocoIndex flow_def for end-to-end
  search/
    retriever.py            # hybrid search + structure expansion
  cli.py
  config.yaml
```

---

# Data model

```python
from dataclasses import dataclass
from typing import Literal, Optional, List, Dict, Tuple

Kind = Literal["def", "ref"]

@dataclass(frozen=True)
class Tag:
    file: str            # relative path
    abs_file: str
    lang: str
    name: str            # identifier text
    kind: Kind           # "def" | "ref"
    line: int            # 0-based, -1 for faux-refs

@dataclass(frozen=True)
class Chunk:
    id: str              # stable hash of file+span+name
    file: str
    abs_file: str
    lang: str
    symbol_kind: str     # class/function/method/type/enum/module...
    name: str
    container: Optional[str]  # parent class/module name
    start_line: int
    end_line: int
    header: str          # "path:line  kind name(sig)"
    body: str            # minimal source (def + a bit of context)
    deps: List[str]      # referenced identifiers (or defining files)
    rank: float          # from PageRank if computed
    sha: str             # file content hash for lineage
```

---

# Step-by-step build

## 0) Config & deps

* Choose **vector DB**: pgvector (recommended), Qdrant, or Milvus. (You’ve used pgvector; we’ll show that.)
* Choose **embedding**: `sentence-transformers/all-MiniLM-L6-v2` (384-d) for local, or `voyage-code-3` for stronger code retrieval. Make this configurable.
* Vendor Aider query files under `queries/tree-sitter-language-pack/`.
  Your TS file shows only `@name.definition.*` captures => no refs emitted; we’ll rely on Pygments for faux-refs in TS until we add `reference.*` captures.

## 1) Tags loader + parser (Aider-style, but as a library)

```python
# codesitter/tags_loader.py
from importlib import resources
from tree_sitter_language_pack import get_language
from grep_ast.tsl import get_parser, USING_TSL_PACK

def load_query(lang: str) -> str | None:
    # Prefer tree-sitter-language-pack; fallback to tree-sitter-languages
    subdirs = ["tree-sitter-language-pack", "tree-sitter-languages"]
    for sub in subdirs:
        try:
            p = resources.files("codeagent").joinpath("queries", sub, f"{lang}-tags.scm")
            if p.exists(): 
                return p.read_text(encoding="utf-8")
        except KeyError:
            pass
    return None

def get_lang_and_parser(lang: str):
    return get_language(lang), get_parser(lang)
```

```python
# codesitter/ts_parser.py
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token

def filename_to_lang(path: str) -> str | None:
    # mirror grep_ast’s logic or a custom mapping
    ...

def parse_file_to_tags(path: str, rel_path: str) -> list[Tag]:
    lang = filename_to_lang(path)
    if not lang: return []
    language, parser = get_lang_and_parser(lang)

    qsrc = load_query(lang)
    if not qsrc: return []  # unsupported lang

    code = open(path, "r", encoding="utf-8", errors="ignore").read()
    tree = parser.parse(code.encode("utf-8"))
    query = language.query(qsrc)

    # USING_TSL_PACK note: captures shape differs; match Aider’s branching
    captures = query.captures(tree.root_node)
    nodes: list[tuple] = []
    if USING_TSL_PACK:
        for tag, ns in captures.items():
            nodes += [(n, tag) for n in ns]
    else:
        nodes = list(captures)

    tags: list[Tag] = []
    saw_def, saw_ref = False, False
    for node, tag in nodes:
        if tag.startswith("name.definition."):
            kind = "def"; saw_def = True
        elif tag.startswith("name.reference."):
            kind = "ref"; saw_ref = True
        else:
            continue
        name = node.text.decode("utf-8", "ignore")
        tags.append(Tag(
            file=rel_path, abs_file=path, lang=lang,
            name=name, kind=kind, line=node.start_point[0],
        ))

    # backfill refs if defs-only (TS case with your tags.scm)
    if saw_def and not saw_ref and code:
        try:
            lex = guess_lexer_for_filename(path, code)
            for tok_type, tok_val in lex.get_tokens(code):
                if tok_type in Token.Name and tok_val.strip():
                    tags.append(Tag(file=rel_path, abs_file=path, lang=lang,
                                    name=tok_val, kind="ref", line=-1))
        except Exception:
            pass

    return tags
```

## 2) Definition spans & compact bodies

* For every **def** tag, find the **AST node** that owns it (function/method/class). Use either a second query (e.g., `@definition.function`) or climb parents by node.type until in `{function_declaration, method_definition, class_declaration, ...}`.
* Render a **compact body**: full signature + body start + a few logical lines; optionally docstring. Aider uses `TreeContext` to produce compact "lines of interest"—we can mirror that behavior or keep it simpler to start.

```python
# codesitter/spans.py
def def_node_for_name(node) -> "Node":
    # climb parents until a known def node
    ...

def slice_source(code: str, node, pad_before=2, pad_after=4):
    start = max(0, node.start_point[0]-pad_before)
    end = node.end_point[0] + pad_after
    lines = code.splitlines()
    return start, end, "\n".join(lines[start:end+1])
```

## 3) Optional: Graph rank like Aider

* Build two maps: `defines[name] -> {files}`, `references[name] -> {files}`.
* Build edges `ref_file → def_file` (weighted by frequency and casing heuristic).
* Run **PageRank** to produce a **file score** and/or **symbol score**.
  Use this **rank** in chunk metadata; use it during retrieval to break ties and to pre-expand context.

## 4) CocoIndex pipeline (incremental)

We’ll define a clear DAG using CocoIndex decorators. (I’m following the same style you’ve used before, e.g. `@cocoindex.op.function()` and `@cocoindex.transform_flow()`.)

```python
# pipeline/ops_parse.py
import cocoindex
from codesitter.ts_parser import parse_file_to_tags

@cocoindex.op.function()
def list_source_files(root_dir: str) -> list[str]:
    # glob by extensions; optionally respect .gitignore
    ...

@cocoindex.op.function()
def stat_file(path: str) -> dict:
    # return {path, mtime, size, sha256} to drive incremental checks
    ...

@cocoindex.op.function()
def parse_to_tags(item: dict) -> list[dict]:
    # item = {"path", "rel_path", "mtime", "sha"}
    tags = parse_file_to_tags(item["path"], item["rel_path"])
    return [vars(t) for t in tags]
```

```python
# pipeline/ops_chunks.py
import cocoindex
from codesitter.spans import slice_source, def_node_for_name

@cocoindex.op.function()
def tags_to_chunks(file_record: dict, tags: list[dict]) -> list[dict]:
    # group tags by def; compute spans using AST; build Chunk dicts
    ...
    return chunks
```

```python
# pipeline/ops_embed.py
import cocoindex

@cocoindex.transform_flow()
def chunk_to_embedding(chunks: cocoindex.DataSlice[dict]) -> cocoindex.DataSlice[list[float]]:
    # choose model via config; support voyage or sentence-transformers
    return chunks.transform(
        cocoindex.functions.SentenceTransformerEmbed(model="sentence-transformers/all-MiniLM-L6-v2")
    )
```

```python
# pipeline/ops_store.py
import cocoindex
import psycopg
from pgvector.psycopg import register_vector

@cocoindex.op.function()
def write_pg(chunks: list[dict], embeddings: list[list[float]], conn_str: str) -> int:
    # upsert by Chunk.id; keep sha & spans; create ivfflat index if missing
    ...
    return len(chunks)
```

```python
# pipeline/flow.py
import cocoindex

@cocoindex.flow_def(name="CodeIndexing")
def build_index(root_dir: str, conn_str: str):
    files = list_source_files(root_dir)
    stats = files.map(stat_file)               # for incrementality
    tags  = stats.map(parse_to_tags)
    chunks = (stats, tags).map(tags_to_chunks) # join on path
    vecs = chunk_to_embedding(chunks)
    _ = (chunks, vecs).map(lambda c,v: write_pg(c, v, conn_str))
```

**Incrementality hooks**

* CocoIndex caches results keyed by **input hash**. Make sure `stat_file` includes mtime/sha; if unchanged, the rest of the chain is skipped automatically.
* Keep a **lineage table** in Postgres (chunk\_id ➜ file\_sha + offsets). On file change, delete old chunks for that file and re-insert.

**Watcher**

* Use `watchfiles` to trigger `build_index(root_dir, conn_str)` on changes (debounced). Aider depends on it too, which is a good signal.

## 5) Vector DB schema (pgvector)

```sql
CREATE TABLE IF NOT EXISTS code_chunks (
  id          TEXT PRIMARY KEY,
  file        TEXT NOT NULL,
  lang        TEXT NOT NULL,
  symbol_kind TEXT,
  name        TEXT,
  container   TEXT,
  start_line  INT,
  end_line    INT,
  header      TEXT,
  body        TEXT,
  deps        JSONB,
  rank        DOUBLE PRECISION,
  sha         TEXT,
  embedding   vector(384)  -- set at runtime if different model
);

-- HNSW or IVFFLAT depending on PG version/extension config
CREATE INDEX IF NOT EXISTS code_chunks_embed_idx
ON code_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS code_chunks_file_idx ON code_chunks(file);
CREATE INDEX IF NOT EXISTS code_chunks_name_idx ON code_chunks(name);
CREATE INDEX IF NOT EXISTS code_chunks_lang_idx ON code_chunks(lang);
```

> If you switch to Voyage or another model, set the correct vector dimension and ops (cosine or L2) at table creation time.

## 6) Retrieval (RAG-compliant)

* **Hybrid query**:

  1. **Lexical**: name/symbol match and file path filter (BM25 or trigram/FTS, or a quick LIKE/GIN if you stay in Postgres).
  2. **Vector**: semantic nearest neighbors on `body` + `header` text.
* **Structure-aware expansion**: When a **def** chunk wins:

  * bring its **container** (e.g., class) and **neighbors** (methods in same class),
  * include **imports** or **local deps** (use `deps` list, or compute on the fly via tags),
  * cap total tokens to a budget (estimate with `tiktoken`).
* **Citations**: always attach `(file, start_line:end_line)` to each context piece.
* **Freshness**: prefer chunks with newest `sha/mtime` for a file when duplicates linger (during reindex windows).

## 7) Quality & eval

* **Unit tests** per language: ensure `definition.*` captures become chunks with sane spans; ensure **refs** appear when definitions-only tags exist (TS case).
* **Golden queries**: build a small suite of “find the class/method” prompts — measure **Recall\@k** and **MRR**.
* **Chunk tuning**: adjust span padding and docstring capture until accuracy stabilizes.
* **Ranking ablation**: compare retrieval with/without the PageRank weight.

---

# Why this matches Aider behavior (and improves it)

* **Same core extraction**: run `*-tags.scm` queries, label `def/ref`, and backfill refs when a language provides only defs (your `typescript-tags.scm` is defs-only).
* **Same context philosophy**: compact, focused code bodies (like `TreeContext`) so the LLM doesn’t drown.
* **Improved RAG shape**: store **symbol-level chunks** with **rich metadata**, enabling **structured filters** and **stitching** (container + deps) during retrieval.
* **Incrementality**: CocoIndex handles change-propagation; you only re-index what changed, propagating to chunks and embeddings automatically.

---

# Next actions (concrete)

1. **Confirm targets**: which languages first? I’ll drop in the right capture names for each (class/function/method/etc.).
2. **Repo path + DB**: share your intended `root_dir` and Postgres DSN.
3. **Embedding choice**: local (MiniLM-L6-v2) vs hosted (Voyage).
4. I’ll generate the **exact** files:

   * `codesitter/tags_loader.py`, `ts_parser.py`, `spans.py`
   * `pipeline/ops_*.py`, `pipeline/flow.py`
   * `search/retriever.py` with a `retrieve(query)` that does hybrid + expansion
   * A small `cli.py` (`codeagent index`, `codeagent query`, `codeagent watch`)

If you want, send me your **top 3 languages** (e.g., TypeScript, Python, Go), and I’ll wire the capture→symbol\_kind mapping and the definition-span logic for those immediately.
