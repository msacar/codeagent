import os
from dataclasses import dataclass
from typing import List
import cocoindex
import json


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
    deps: List[str]
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

    deps = sorted({r["name"] for r in refs})
    # Gather reference line numbers for LOI selection (ignore faux refs: line == -1)
    ref_lines = sorted(
        {
            int(r["line"])
            for r in refs
            if isinstance(r.get("line"), int) and r["line"] >= 0
        }
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
        # Prefer condensed, Aider-style "lines of interest" within the def span.
        # Fallback to contiguous slicing if nothing was selected.
        loi_pad = 3
        max_lines = (
            80 if d["symbol_kind"] in ("function", "method", "constructor") else 60
        )
        sline, eline, body = condense_symbol_body(
            code_s=code_s,
            def_start=d["start_line"],
            def_end=d["end_line"],
            ref_lines=ref_lines,
            pad=loi_pad,
            max_lines=max_lines,
        )
        if not body:
            pad = 12 if d["symbol_kind"] in ("function", "method", "constructor") else 6
            sline, eline, body = slice_body(
                code_s, d["start_line"], d["end_line"], pad_after=pad
            )

        header = f"{rel}:L{sline}  {d['symbol_kind']} {d['name']}".strip()
        cid = stable_id(rel, d["name"], d["symbol_kind"], sline, eline)
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
            start_line=sline,
            end_line=eline,
            header=header,
            body=((d.get("doc") + "\n") if d.get("doc") else "") + body,
            deps=deps,
            rank=symbol_rank,  # Use computed PageRank
            sha=sha,
            text=text,
        )
        out.append(chunk)  # return dataclass instances (Struct rows)
    return out
