from __future__ import annotations
import os
import cocoindex
from ..codesitter.parser import parse_defs_and_refs


@cocoindex.op.function()
class parse_file_to_symbols:
    """
    Parse a single file to SymbolDef[] and RefTag[] using Tree-sitter queries.
    """
    def __call__(self, filename: str, path: str) -> dict:
        rel = os.path.relpath(path, start=os.getcwd())
        defs, refs = parse_defs_and_refs(path, rel)
        return {
            "defs": [d.__dict__ for d in defs],
            "refs": [r.__dict__ for r in refs],
        }

