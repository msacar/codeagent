import cocoindex
import json
from typing import Dict, List, TypedDict, Any, cast
from ..codesitter.parser import parse_defs_and_refs_from_text


class SymbolsResult(TypedDict):
    defs: List[Dict[str, Any]]
    refs: List[Dict[str, Any]]

@cocoindex.op.function()
def parse_file_to_symbols(content: str, filename: str) -> str:
    """
    Parse a single file to SymbolDef[] and RefTag[] using Tree-sitter queries.
    Returns a JSON string: {"defs": [...], "refs": [...]}.
    """
    rel = filename  # LocalFile's filename is already relative to the source root
    defs, refs = parse_defs_and_refs_from_text(filename, rel, content or "")
    payload = {
            "defs": [d.__dict__ for d in defs],
            "refs": [r.__dict__ for r in refs],
    }
    # JSON is a supported scalar type for CocoIndex op outputs.
    return json.dumps(payload, ensure_ascii=False)


