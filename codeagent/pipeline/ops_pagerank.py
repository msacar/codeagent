"""
PageRank operations for the CocoIndex pipeline.
Collects all symbols across files and computes ranks.
"""

import json
from typing import List
import cocoindex
from ..pagerank import CodePageRank


@cocoindex.op.function()
def calculate_pagerank(all_symbols: List[str]) -> str:
    """
    Calculate PageRank scores from all collected symbols.
    Input: List of JSON strings {"file": ..., "defs": [...], "refs": [...]}
    Output: JSON string with file and symbol ranks
    """
    ranker = CodePageRank()

    # Collect all definitions and references
    for sym_json in all_symbols:
        if not sym_json:
            continue
        data = json.loads(sym_json)
        file = data.get("file", "")
        defs = data.get("defs", [])
        refs = data.get("refs", [])

        # Add definitions
        def_names = [d["name"] for d in defs if d.get("name")]
        if def_names:
            ranker.add_definitions(file, def_names)

        # Add references
        ref_names = [r["name"] for r in refs if r.get("name")]
        if ref_names:
            ranker.add_references(file, ref_names)

    # Calculate ranks
    file_ranks = ranker.calculate_ranks()
    symbol_ranks = ranker.get_symbol_ranks(file_ranks)

    # Convert to serializable format
    symbol_ranks_dict = {
        f"{file}:{symbol}": rank for (file, symbol), rank in symbol_ranks.items()
    }

    result = {"file_ranks": file_ranks, "symbol_ranks": symbol_ranks_dict}

    return json.dumps(result, ensure_ascii=False)


@cocoindex.op.function()
def enrich_symbols_with_rank(syms: str, filename: str, ranks_json: str) -> str:
    """
    Enrich symbol data with PageRank scores.
    """
    data = json.loads(syms or "{}")
    ranks = json.loads(ranks_json or "{}")

    file_rank = ranks.get("file_ranks", {}).get(filename, 0.0)
    symbol_ranks = ranks.get("symbol_ranks", {})

    # Add rank to each definition
    for d in data.get("defs", []):
        symbol_key = f"{filename}:{d.get('name', '')}"
        d["rank"] = symbol_ranks.get(symbol_key, file_rank)

    # Add file rank as metadata
    data["file_rank"] = file_rank

    return json.dumps(data, ensure_ascii=False)
