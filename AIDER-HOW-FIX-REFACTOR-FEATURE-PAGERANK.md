Short answer: Aider doesn’t guess individual function bodies from the whole repo. It gives the LLM:

1. the **full text** of files you’ve explicitly “added to chat” (those are what get edited), and
2. a compact **repo map** for the rest of the repo (just file lists + key symbol definitions/signatures + a few “critical lines”), chosen to fit a token budget via a **graph-ranking** pass. From that map the LLM decides which *other* files it needs and asks Aider to add them; the `/context` command can now auto-identify those files too. ([Aider][1])

Here’s the flow Aider uses:

* **Build a repo map (once, then refresh as needed).** Tree-sitter queries extract symbol definitions (classes/functions/methods) and their names/signatures; the map shows “critical lines” around each definition so the LLM understands APIs without full bodies. ([Aider][2])
* **Rank & trim the map to fit tokens.** It constructs a dependency graph (nodes = files; edges = uses/depends-on) and runs a PageRank-style algorithm to select the most relevant slices that will fit within the current `--map-tokens` budget. ([Aider][2])
* **Send context with every request.** Aider always sends (a) your chat files’ **full content** plus (b) the **trimmed repo map**. If the LLM decides it needs more than the signatures/critical lines (e.g., a function body in another file), it **asks to add that file** and Aider offers to include it. ([Aider][2])
* **Auto-picking targets (new).** The `/context` command can “automatically identify which files need to be edited” for a request, essentially using the same map/graph signals to propose files to add. ([Aider][3], [Reddit][4])

What this means for feature/bug-fix/refactor:

* **Feature:** You add the likely target file(s). Aider sends those bodies + a ranked map of related modules/interfaces. The LLM may ask to add adjacent files (e.g., routes, types) once it sees signatures. ([Aider][1])
* **Bug fix:** If you don’t add files, Aider still sends a map; the LLM can use it to pinpoint the module that defines the faulty function and request that file’s body. Or run `/context` to let Aider propose the edit set. ([Aider][2])
* **Refactor:** Sae pattern—chat files contain bodies; the map supplies cross-references so the LLM can find all impacted symbols and then ask to include more files if needed. ([Aider][2])

If you want, I can mirror this behavior in your pipeline: send **full text only for “edit set” files**, and for everything else send a **ranked, token-capped map** (defs + short context). That’ll match Aider’s strategy closely without maintaining per-language rules.

[1]: https://aider.chat/docs/usage.html?utm_source=chatgpt.com "Usage"
[2]: https://aider.chat/docs/repomap.html?utm_source=chatgpt.com "Repository map"
[3]: https://aider.chat/HISTORY.html?utm_source=chatgpt.com "Release history"
[4]: https://www.reddit.com/r/ChatGPTCoding/comments/1jk0al8/aider_v0790_supports_new_sota_gemini_25_pro/?utm_source=chatgpt.com "Aider v0.79.0 supports new SOTA Gemini 2.5 Pro"
