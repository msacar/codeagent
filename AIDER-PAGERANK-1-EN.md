I dug through the Aider sources you shared—here’s exactly how Aider handles this, and why it never bumps into your “constructor mislabeled / empty method name” problem:

* **Aider doesn’t track symbol kinds at all.** In the repo-map pass it only cares about *names* and whether a capture is a **def** or a **ref**. It looks at Tree-sitter query captures and keeps anything whose tag starts with `name.definition.` (def) or `name.reference.` (ref). The “kind” it records is just `"def"` or `"ref"`, not `"class" | "method" | "constructor"`. Names are taken straight from `node.text`.&#x20;

* **If a language’s queries don’t produce refs, Aider backfills refs with a tokenizer pass.** After seeing defs with no refs, it runs Pygments, collects every `Token.Name`, and treats those as refs. That keeps the graph dense enough for ranking without doing any language-specific inference.&#x20;

* **Query file selection mirrors what you described.** It prefers `queries/tree-sitter-language-pack/{lang}-tags.scm` when running with the language pack, and falls back to `queries/tree-sitter-languages/{lang}-tags.scm`. So the “two folders” you noticed are both supported; the pack is preferred when present.&#x20;

* **All downstream logic is name-based, not kind-based.** Aider builds a PageRank graph from “who references which defined identifier” and weights edges; there’s no constructor/method/class logic anywhere in that ranking. Later it renders context with `TreeContext` using the lines where those *name* nodes occur. Again: no symbol-kind classification. &#x20;

### What that means for you

If you want to behave “like Aider” (and avoid maintaining per-language rules):

* In your **parse stage**, emit records keyed off **`name.definition.*`** and **`name.reference.*`** only, and drop any attempt to decide `"class" | "method" | "constructor"` there. That’s precisely what Aider does.&#x20;
* If refs are missing for a language, you can adopt Aider’s simple **token backfill** so your def/ref graph stays useful without extra SCM work.&#x20;
* If your **chunker** currently depends on `symbol_kind` for padding, just add a **sane default** (treat unknown kind as “function-like” padding). That keeps chunk quality high without language-specific normalization—this is why Aider avoids the whole constructor edge case in the first place.

If you want, I can adjust your `ops_parse.py` to emit only Aider-style `{"name", "kind": "def|ref", "line"}` (plus file/lang), and tweak `symbols_to_chunks` so it doesn’t rely on per-language kinds. That will make your pipeline match Aider’s behavior 1:1 while keeping your SCM files untouched.
