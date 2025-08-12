"""
Batch PageRank processor for computing code importance.
This runs as a separate pass after initial parsing to compute global ranks.
"""

import os
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from fnmatch import fnmatch
from ..pagerank import CodePageRank
from ..codesitter.parser import parse_defs_and_refs


class BatchPageRankProcessor:
    """
    Processes all code files to build a dependency graph and compute PageRank scores.
    This follows Aider's approach: parse all files, build graph, rank, then use ranks.
    """

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or os.getenv("CODEAGENT_ROOT", os.getcwd())
        self.ranker = CodePageRank()
        self._file_ranks: Dict[str, float] = {}
        self._symbol_ranks: Dict[Tuple[str, str], float] = {}

    def process_directory(
        self, patterns: List[str] = None, exclude_patterns: List[str] = None
    ) -> Dict[str, float]:
        """
        Process all matching files in the directory and compute PageRank.
        Returns file ranks.
        """
        if patterns is None:
            patterns = ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py"]

        if exclude_patterns is None:
            exclude_patterns = [
                "**/node_modules/**",
                "**/dist/**",
                "**/build/**",
                "**/.git/**",
                "**/.idea/**",
                "**/__pycache__/**",
            ]

        root_path = Path(self.root_dir)
        processed_files = set()

        # Collect all matching files
        for pattern in patterns:
            for file_path in root_path.glob(pattern):
                rel_path = str(file_path.relative_to(root_path))
                # Check exclusions on the relative path for predictable ** semantics
                if any(fnmatch(rel_path, exc) for exc in exclude_patterns):
                    continue

                if rel_path not in processed_files:
                    self._process_file(str(file_path), rel_path)
                    processed_files.add(rel_path)

        # Calculate PageRank
        self._file_ranks = self.ranker.calculate_ranks()
        self._symbol_ranks = self.ranker.get_symbol_ranks(self._file_ranks)

        return self._file_ranks

    def _process_file(self, abs_path: str, rel_path: str):
        """Process a single file to extract definitions and references."""
        try:
            defs, refs = parse_defs_and_refs(abs_path, rel_path)

            # Add definitions
            def_names = [d.name for d in defs if d.name]
            if def_names:
                self.ranker.add_definitions(rel_path, def_names)

            # Add references
            ref_names = [r.name for r in refs if r.name]
            if ref_names:
                self.ranker.add_references(rel_path, ref_names)

        except Exception as e:
            print(f"Error processing {rel_path}: {e}")

    def get_file_rank(self, file: str) -> float:
        """Get the PageRank score for a file."""
        return self._file_ranks.get(file, 0.0)

    def get_symbol_rank(self, file: str, symbol: str) -> float:
        """Get the PageRank score for a symbol in a file."""
        return self._symbol_ranks.get((file, symbol), 0.0)

    def get_top_files(self, n: int = 10) -> List[Tuple[str, float]]:
        """Get the top N files by PageRank."""
        sorted_ranks = sorted(
            self._file_ranks.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_ranks[:n]

    def get_top_symbols(self, n: int = 20) -> List[Tuple[Tuple[str, str], float]]:
        """Get the top N symbols by PageRank."""
        sorted_ranks = sorted(
            self._symbol_ranks.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_ranks[:n]

    def save_ranks(self, output_path: str):
        """Save computed ranks to a JSON file."""
        data = {
            "file_ranks": self._file_ranks,
            "symbol_ranks": {
                f"{file}:{symbol}": rank
                for (file, symbol), rank in self._symbol_ranks.items()
            },
        }
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_ranks(self, input_path: str):
        """Load pre-computed ranks from a JSON file."""
        with open(input_path, "r") as f:
            data = json.load(f)

        self._file_ranks = data.get("file_ranks", {})
        self._symbol_ranks = {}

        for key, rank in data.get("symbol_ranks", {}).items():
            if ":" in key:
                file, symbol = key.rsplit(":", 1)
                self._symbol_ranks[(file, symbol)] = rank


# Global instance for reuse across pipeline operations
_global_ranker: Optional[BatchPageRankProcessor] = None


def get_global_ranker() -> BatchPageRankProcessor:
    """Get or create the global PageRank processor."""
    global _global_ranker
    if _global_ranker is None:
        _global_ranker = BatchPageRankProcessor()
        # Process directory on first access
        _global_ranker.process_directory()
    return _global_ranker


def compute_pagerank_batch(root_dir: Optional[str] = None) -> Dict[str, float]:
    """
    Compute PageRank for all files in a directory.
    This is meant to be called before the main pipeline.
    """
    processor = BatchPageRankProcessor(root_dir)
    return processor.process_directory()
