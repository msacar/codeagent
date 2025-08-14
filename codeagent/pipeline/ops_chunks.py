import os
from dataclasses import dataclass
from typing import List, Dict
import cocoindex
import json
import re
from collections import Counter


from ..codesitter.spans import file_sha, slice_body, stable_id
from ..codesitter.condense import condense_symbol_body


@dataclass(frozen=True)
class Chunk:
    id: str
    file: str
    abs_file: str
    lang: str
    symbol_kind: str
    name: str
    container: str | None
    start_line: int
    end_line: int
    header: str
    body: str
    deps: Dict[str, int]
    rank: float
    sha: str
    text: str


@cocoindex.op.function()
def symbols_to_chunks(syms: str, filename: str, content: str) -> List[Chunk]:
    """
    Convert parsed defs/refs for a file to a list of chunks.
    Inputs:
      - syms: JSON string {"defs": [...], "refs": [...]}
      - filename: relative filename (from LocalFile)
      - content: file content (text)
    """
    # `filename` from LocalFile is relative to the source root; rebuild abs path for metadata.
    root_dir = os.getenv("CODEAGENT_ROOT", os.getcwd())
    abs_path = os.path.join(root_dir, filename)

    rel = filename
    # Ensure content is str
    code_s = content or ""
    code_b = code_s.encode("utf-8", "ignore")
    sha = file_sha(code_b)
    data = json.loads(syms or "{}")
    defs = data.get("defs", [])
    refs = data.get("refs", [])

    # Keep reference *counts* per identifier (better edge weights for PR)
    dep_counts: Dict[str, int] = dict(
        Counter([r["name"] for r in refs if r.get("name")])
    )

    # Get PageRank scores if available
    try:
        from .batch_pagerank import get_global_ranker

        ranker = get_global_ranker()
        file_rank = ranker.get_file_rank(rel)
    except Exception:
        # Fallback if PageRank not computed
        file_rank = 0.0
        ranker = None

    out: List[Chunk] = []
    for d in defs:
        # Default post padding by kind (to mimic Aider's emphasis on funcs/methods)
        default_post = (
            12 if d["symbol_kind"] in ("function", "method", "constructor") else 6
        )

        # Aider-style LOI condenser knobs from env
        pad_before = int(os.getenv("CODEAGENT_LOI_PRE", "2"))
        pad_after = int(os.getenv("CODEAGENT_LOI_POST", str(default_post)))
        max_lines_env = os.getenv("CODEAGENT_LOI_MAX_LINES")
        max_lines = int(max_lines_env) if max_lines_env else 80
        tokens_env = os.getenv("CODEAGENT_MAP_TOKENS")
        token_budget = int(tokens_env) if tokens_env else None
        hilite = os.getenv("CODEAGENT_LOI_HILITE", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        mark = os.getenv("CODEAGENT_LOI_MARK", "▶")

        # Build anchors: signature line + any lines inside the span referencing known identifiers
        file_lines = code_s.splitlines()
        span_start_1 = d["start_line"] + 1
        span_end_1 = d["end_line"] + 1
        anchors = {span_start_1}
        if dep_counts and span_start_1 <= span_end_1:
            idents = [
                x
                for x in dep_counts.keys()
                if x and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", x)
            ]
            if idents:
                rx = re.compile(
                    r"\b(" + "|".join(re.escape(x) for x in idents) + r")\b"
                )
                for L in range(span_start_1, span_end_1 + 1):
                    line_txt = file_lines[L - 1] if L - 1 < len(file_lines) else ""
                    if rx.search(line_txt):
                        anchors.add(L)

        s1, e1, condensed = condense_symbol_body(
            file_lines,
            span_start_1,
            span_end_1,
            sorted(anchors),
            pad_before=pad_before,
            pad_after=pad_after,
            max_lines=max_lines,
            token_budget=token_budget,
            hilite_anchors=hilite,
            mark=mark,
        )

        # Fallback to a simple tail pad if condenser produced nothing (very rare)
        if not condensed:
            _, _, condensed = slice_body(
                code_s, d["start_line"], d["end_line"], pad_after=default_post
            )
            s1, e1 = span_start_1, span_end_1

        header = f"{rel}:L{s1}  {d['symbol_kind']} {d['name']}".strip()
        cid = stable_id(rel, d["name"], d["symbol_kind"], s1, e1)
        body = ((d.get("doc") + "\n") if d.get("doc") else "") + condensed
        text = header + "\n" + body

        # Get symbol-specific rank if available
        if ranker:
            symbol_rank = ranker.get_symbol_rank(rel, d["name"])
        else:
            symbol_rank = file_rank

        chunk = Chunk(
            id=cid,
            file=rel,
            abs_file=abs_path,
            lang=d["lang"],
            symbol_kind=d["symbol_kind"],
            name=d["name"],
            container=d.get("container"),
            start_line=s1,
            end_line=e1,
            header=header,
            body=body,
            deps=dep_counts,
            rank=symbol_rank,  # Use computed PageRank
            sha=sha,
            text=text,
        )
        out.append(chunk)  # return dataclass instances (Struct rows)
    return out
