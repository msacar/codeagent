from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List, Dict, Any
import cocoindex

from ..codesitter.spans import file_sha, slice_body, stable_id


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
def symbols_to_chunks(path: str, filename: str, syms: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert parsed defs/refs for a file to a list of chunks.
    Inputs:
      - path: absolute file path
      - filename: relative filename (from LocalFile)
      - syms: {"defs": [...], "refs": [...]}
    """
    rel = os.path.relpath(path, start=os.getcwd())
    code_b = open(path, "rb").read()
    code_s = code_b.decode("utf-8", "ignore")
    sha = file_sha(code_b)
    defs = syms.get("defs", [])
    refs = syms.get("refs", [])
    deps = sorted({r["name"] for r in refs})

    out: List[Dict[str, Any]] = []
    for d in defs:
        pad = 12 if d["symbol_kind"] in ("function", "method", "constructor") else 6
        sline, eline, body = slice_body(code_s, d["start_line"], d["end_line"], pad_after=pad)
        header = f"{rel}:L{sline}  {d['symbol_kind']} {d['name']}".strip()
        cid = stable_id(rel, d["name"], d["symbol_kind"], sline, eline)
        text = header + "\n" + body
        chunk = Chunk(
            id=cid,
            file=rel,
            abs_file=path,
            lang=d["lang"],
            symbol_kind=d["symbol_kind"],
            name=d["name"],
            container=d.get("container"),
            start_line=sline,
            end_line=eline,
            header=header,
            body=((d.get("doc") + "\n") if d.get("doc") else "") + body,
            deps=deps,
            rank=0.0,
            sha=sha,
            text=text,
        )
        out.append(chunk.__dict__)
    return out